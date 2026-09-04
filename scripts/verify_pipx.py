"""Build Mongrove and smoke-test an isolated pipx installation."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Install the wheel in temporary pipx paths and validate its entry point."""

    pipx_executable = shutil.which("pipx")
    pipx = [pipx_executable] if pipx_executable is not None else [sys.executable, "-m", "pipx"]
    try:
        _run([*pipx, "--version"])
    except subprocess.CalledProcessError as error:
        raise SystemExit(
            "pipx is required. Install it with: python -m pip install --user pipx"
        ) from error

    with tempfile.TemporaryDirectory(prefix="mongrove-pipx-") as temporary:
        temporary_path = Path(temporary)
        wheel_dir = temporary_path / "wheel"
        pipx_home = temporary_path / "pipx-home"
        pipx_bin = temporary_path / "pipx-bin"
        environment = os.environ | {
            "PIPX_HOME": str(pipx_home),
            "PIPX_BIN_DIR": str(pipx_bin),
        }
        _run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(wheel_dir), str(ROOT)])
        wheels = sorted(wheel_dir.glob("mongrove-*.whl"))
        if len(wheels) != 1:
            raise RuntimeError("Expected exactly one Mongrove wheel.")
        _run([*pipx, "install", str(wheels[0])], environment)
        executable = pipx_bin / ("mongrove.exe" if os.name == "nt" else "mongrove")
        _run([str(executable), "--version"], environment)
    return 0


def _run(command: list[str], environment: dict[str, str] | None = None) -> None:
    subprocess.run(command, check=True, cwd=ROOT, env=environment)


if __name__ == "__main__":
    raise SystemExit(main())
