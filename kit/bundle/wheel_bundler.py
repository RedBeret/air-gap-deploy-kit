"""Python wheel bundler — downloads packages offline using pip download."""

from __future__ import annotations

import subprocess
from pathlib import Path

from kit.bundle.manifest import WheelEntry, sha256_file

# Default packages to bundle (dogfooding fde-data-forge and rag-eval-bench)
DEFAULT_PACKAGES = [
    "fde-data-forge",
    "rag-eval-bench",
    "air-gap-deploy-kit",
]


def _run(cmd: list[str], *, runner=None) -> str:
    if runner is not None:
        return runner(cmd)
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def download_wheels(
    packages: list[str],
    bundle_dir: Path,
    python_version: str = "3.11",
    *,
    runner=None,
) -> list[WheelEntry]:
    """
    Use `pip download` to collect wheels + dependencies into bundle_dir/wheels/.
    Returns a list of WheelEntry records for the manifest.

    Each entry includes a SHA-256 checksum for integrity verification at deploy time.
    """
    wheels_dir = bundle_dir / "wheels"
    wheels_dir.mkdir(parents=True, exist_ok=True)

    # pip download collects the wheel files
    cmd = [
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
