"""Collect prebuilt local wheels and optionally download published packages."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from kit.bundle.manifest import WheelEntry, sha256_file

# Portfolio packages are not published to PyPI. Callers must provide published
# package names or a local wheelhouse explicitly.
DEFAULT_PACKAGES: list[str] = []


def _run(cmd: list[str], *, runner=None) -> str:
    if runner is not None:
        return runner(cmd)
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def download_wheels(
    packages: list[str],
    bundle_dir: Path,
    python_version: str = "3.12",
    *,
    wheel_sources: list[Path] | None = None,
    runner=None,
) -> list[WheelEntry]:
    """
    Copy wheels from local files/directories and use ``pip download`` only for
    explicit published package names.
    Returns a list of WheelEntry records for the manifest.

    Each entry includes a SHA-256 checksum for integrity verification at deploy time.
    """
    wheels_dir = bundle_dir / "wheels"
    wheels_dir.mkdir(parents=True, exist_ok=True)

    for source in wheel_sources or []:
        candidates = [source] if source.is_file() else sorted(source.glob("*.whl"))
        if not candidates:
            raise ValueError(f"No wheel files found in {source}")
        for wheel in candidates:
            if wheel.suffix != ".whl":
                raise ValueError(f"Wheel source is not a .whl file: {wheel}")
            destination = wheels_dir / wheel.name
            if destination.exists() and sha256_file(destination) != sha256_file(wheel):
                raise ValueError(f"Conflicting wheel filename: {wheel.name}")
            if not destination.exists():
                shutil.copy2(wheel, destination)

    if packages:
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--dest",
            str(wheels_dir),
            "--python-version",
            python_version,
            "--only-binary=:all:",
            *packages,
        ]
        _run(cmd, runner=runner)

    # Build manifest entries for everything in the wheels dir
    entries: list[WheelEntry] = []
    for whl_path in sorted(wheels_dir.glob("*.whl")):
        # Derive package name from filename (PEP 427: {name}-{version}-...)
        parts = whl_path.stem.split("-")
        package_label = f"{parts[0]}=={parts[1]}" if len(parts) >= 2 else parts[0]
        checksum = sha256_file(whl_path)
        entries.append(
            WheelEntry(
                package=package_label,
                filename=whl_path.name,
                sha256=checksum,
            )
        )

    return entries
