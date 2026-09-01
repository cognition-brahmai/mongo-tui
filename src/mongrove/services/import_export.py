"""Streaming BSON-aware document export jobs."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol

from mongrove.domain.query import FindQuery
from mongrove.services.bson_codec import to_canonical_extended_json, to_extended_json
from mongrove.services.mongo_gateway import FindStreamResult


class ExportFormat(str, Enum):
    """Supported output encodings for a find-query export."""

    JSON = "json"
    EJSON = "ejson"
    CSV = "csv"


@dataclass(frozen=True, slots=True)
class ExportRequest:
    """Validated destination and format choices for one immutable find query."""

    destination: Path
    format: ExportFormat
    csv_columns: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExportProgress:
    """Throttled in-flight export statistics safe to display in the UI."""

    documents_written: int
    bytes_written: int
    elapsed_ms: int


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Completed atomic export metadata."""

    destination: Path
    documents_written: int
    bytes_written: int
    elapsed_ms: int


class ExportError(RuntimeError):
    """A user-facing local export failure."""


class ExportCancelled(RuntimeError):
    """Raised after a cooperative cancellation removes the staged output file."""


class DocumentStreamGateway(Protocol):
    """Minimal gateway surface required by the streaming local exporter."""

    def stream_documents(
        self,
        database: str,
        collection: str,
        query: FindQuery,
        *,
        consume: Callable[[dict[str, Any]], None],
        is_cancelled: Callable[[], bool],
        batch_size: int = 100,
    ) -> FindStreamResult:
        """Consume documents incrementally without returning a cursor."""
        ...


def parse_export_format(value: str) -> ExportFormat:
    """Parse a case-insensitive format value from the keyboard-first modal."""

    try:
        return ExportFormat(value.strip().casefold())
    except ValueError as error:
        raise ExportError("Format must be json, ejson, or csv.") from error


def parse_csv_columns(value: str) -> tuple[str, ...]:
    """Validate an ordered JSON array of top-level CSV field names."""

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise ExportError("CSV columns must be a JSON array of field names.") from error
    if not isinstance(parsed, list) or not parsed:
        raise ExportError("CSV columns must contain at least one field name.")
    columns = tuple(item for item in parsed if isinstance(item, str) and item.strip())
    if len(columns) != len(parsed):
        raise ExportError("CSV columns must contain non-empty string field names.")
    if len(set(columns)) != len(columns):
        raise ExportError("CSV columns cannot contain duplicate field names.")
    return columns


def export_find_query(
    gateway: DocumentStreamGateway,
    database: str,
    collection: str,
    query: FindQuery,
    request: ExportRequest,
    *,
    is_cancelled: Callable[[], bool],
    on_progress: Callable[[ExportProgress], None] | None = None,
) -> ExportResult:
    """Export a full find cursor through a same-directory atomic staging file."""

    destination = _validate_destination(request.destination)
    if request.format is ExportFormat.CSV and not request.csv_columns:
        raise ExportError("CSV exports require at least one top-level field column.")
    started = perf_counter()
    temporary_path: Path | None = None
    committed = False
    documents_written = 0
    last_reported_at = 0.0

    try:
        descriptor, raw_path = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".part",
            dir=destination.parent,
        )
        temporary_path = Path(raw_path)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as output:
            writer = _DocumentWriter(output, request)
            writer.begin()

            def consume(document: dict[str, Any]) -> None:
                nonlocal documents_written, last_reported_at
                writer.write(document)
                documents_written += 1
                now = perf_counter()
                if on_progress and (
                    documents_written % 100 == 0 or now - last_reported_at >= 0.25
                ):
                    last_reported_at = now
                    on_progress(
                        ExportProgress(
                            documents_written=documents_written,
                            bytes_written=output.tell(),
                            elapsed_ms=_elapsed_ms(started),
                        )
                    )

            stream_result = gateway.stream_documents(
                database,
                collection,
                query,
                consume=consume,
                is_cancelled=is_cancelled,
            )
            if stream_result.cancelled or is_cancelled():
                raise ExportCancelled("Export cancelled before the destination was changed.")
            writer.finish()
            output.flush()
            os.fsync(output.fileno())

        if is_cancelled():
            raise ExportCancelled("Export cancelled before the destination was changed.")
        os.replace(temporary_path, destination)
        committed = True
        bytes_written = destination.stat().st_size
        result = ExportResult(
            destination=destination,
            documents_written=documents_written,
            bytes_written=bytes_written,
            elapsed_ms=_elapsed_ms(started),
        )
        if on_progress:
            on_progress(
                ExportProgress(
                    documents_written=result.documents_written,
                    bytes_written=result.bytes_written,
                    elapsed_ms=result.elapsed_ms,
                )
            )
        return result
    except ExportCancelled:
        raise
    except (OSError, csv.Error, TypeError, ValueError) as error:
        raise ExportError(f"Could not export documents: {error}") from error
    finally:
        if not committed and temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


class _DocumentWriter:
    """Format-specific streaming writer that retains no result documents."""

    def __init__(self, output: Any, request: ExportRequest) -> None:
        self._output = output
        self._request = request
        self._first_document = True
        self._csv_writer: Any = None

    def begin(self) -> None:
        if self._request.format is ExportFormat.CSV:
            self._csv_writer = csv.writer(self._output, lineterminator="\n")
            self._csv_writer.writerow(self._request.csv_columns)
        else:
            self._output.write("[\n")

    def write(self, document: dict[str, Any]) -> None:
        if self._request.format is ExportFormat.CSV:
            if self._csv_writer is None:
                raise AssertionError("CSV writer was not initialized.")
            self._csv_writer.writerow(
                [
                    to_canonical_extended_json(document[column], indent=None)
                    if column in document
                    else ""
                    for column in self._request.csv_columns
                ]
            )
            return
        if not self._first_document:
            self._output.write(",\n")
        serializer = (
            to_extended_json
            if self._request.format is ExportFormat.JSON
            else to_canonical_extended_json
        )
        self._output.write(serializer(document, indent=None))
        self._first_document = False

    def finish(self) -> None:
        if self._request.format is not ExportFormat.CSV:
            self._output.write("\n]\n")


def _validate_destination(destination: Path) -> Path:
    path = destination.expanduser()
    if not path.name:
        raise ExportError("Choose a file path, not a directory.")
    parent = path.parent
    if not parent.exists() or not parent.is_dir():
        raise ExportError("The export destination directory must already exist.")
    if path.exists() and path.is_dir():
        raise ExportError("Choose a file path, not a directory.")
    return path


def _elapsed_ms(started: float) -> int:
    return max(round((perf_counter() - started) * 1_000), 0)
