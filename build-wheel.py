"""Build the project wheel and upload it to PyPI."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
TOKEN_VARIABLE = "PYPI_TOKEN"


def main() -> int:
    """Build one wheel, retain it in dist/, and publish it with Twine."""

    token = _read_token(ROOT / ".env")
    _require_module("build")
    _require_module("twine")

    with tempfile.TemporaryDirectory(prefix="mongrove-wheel-") as temporary:
        wheel_dir = Path(temporary)
        _run(
            [
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "--outdir",
                str(wheel_dir),
            ]
        )

        wheels = list(wheel_dir.glob("*.whl"))
        if len(wheels) != 1:
            raise RuntimeError("Expected the build to produce exactly one wheel.")

        dist_dir = ROOT / "dist"
        dist_dir.mkdir(exist_ok=True)
        wheel = dist_dir / wheels[0].name
        shutil.copy2(wheels[0], wheel)

        environment = os.environ | {
            "TWINE_USERNAME": "__token__",
            "TWINE_PASSWORD": token,
        }
        _run(
            [
                sys.executable,
                "-m",
                "twine",
                "upload",
                "--non-interactive",
                str(wheel),
            ],
            environment,
        )
    return 0


def _read_token(path: Path) -> str:
    """Read PYPI_TOKEN from a simple dotenv file without loading it globally."""

    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError as error:
        raise SystemExit(
            f"{path.name} is required. Add {TOKEN_VARIABLE}=pypi-... to it."
        ) from error

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").lstrip()

        key, separator, value = line.partition("=")
        if separator and key.strip() == TOKEN_VARIABLE:
            token = _unquote(value.strip())
            if token:
                return token
            break

    raise SystemExit(f"{TOKEN_VARIABLE} is missing or empty in {path.name}.")


def _unquote(value: str) -> str:
    """Accept the quoted and unquoted token forms commonly used in dotenv files."""

    if len(value) >= 2 and value[0] in {"'", '"'} and value[-1] == value[0]:
        return value[1:-1]
    return value


def _require_module(module: str) -> None:
    """Give a useful setup error before starting a release build."""

    if importlib.util.find_spec(module) is None:
        raise SystemExit(
            f"{module} is required. Install development dependencies with: "
            f"{sys.executable} -m pip install -e \".[dev]\""
        )


def _run(command: list[str], environment: dict[str, str] | None = None) -> None:
    subprocess.run(command, check=True, cwd=ROOT, env=environment)


if __name__ == "__main__":
    raise SystemExit(main())
