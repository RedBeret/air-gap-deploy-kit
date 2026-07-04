"""Offline installer — loads Docker images and installs wheels from bundle."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from kit.bundle.manifest import (
    BundleManifest,
    load_manifest,
    verify_file_checksums,
    verify_wheel_checksums,
)


@dataclass
class InstallResult:
    """Outcome of a single install step."""

    component: str
    success: bool
    message: str


def _run(cmd: list[str], *, runner=None) -> tuple[bool, str]:
    """
    Run a shell command. Returns (success, output).
    If runner is provided, delegate (for testing).
    """
    if runner is not None:
        try:
            output = runner(cmd)
            return True, output
        except Exception as exc:
            return False, str(exc)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as exc:
        return False, (exc.stderr or exc.stdout or str(exc)).strip()


def load_docker_images(
    manifest: BundleManifest,
    bundle_dir: Path,
    *,
    runner=None,
) -> list[InstallResult]:
    """
    Load each Docker .tar from bundle_dir/docker/ using `docker load`.
    Skips images already present with matching digest.
    """
    results: list[InstallResult] = []
    docker_dir = bundle_dir / "docker"

    for entry in manifest.docker:
        tar_path = docker_dir / entry.filename
        if not tar_path.exists():
            results.append(
                InstallResult(
                    component=entry.image,
                    success=False,
                    message=f"Missing tar file: {tar_path}",
                )
            )
            continue

        # Check if image already loaded with correct digest
        ok, digest = _run(
            ["docker", "inspect", "--format={{.Id}}", entry.image],
            runner=runner,
        )
        if ok and digest.strip() == entry.digest.strip():
            results.append(
                InstallResult(
                    component=entry.image,
                    success=True,
                    message="Already present (digest match) — skipped",
                )
            )
            continue

        ok, out = _run(["docker", "load", "-i", str(tar_path)], runner=runner)
        results.append(
            InstallResult(
                component=entry.image,
                success=ok,
                message=out if ok else f"docker load failed: {out}",
            )
        )

    return results


def install_wheels(
    manifest: BundleManifest,
    bundle_dir: Path,
    *,
    runner=None,
) -> list[InstallResult]:
    """
    Install Python wheels from bundle_dir/wheels/ using pip with --no-index.
    Verifies checksums before installing.
    """
    results: list[InstallResult] = []
    wheels_dir = bundle_dir / "wheels"

    # Checksum verification first
    errors = verify_wheel_checksums(manifest, bundle_dir)
    if errors:
        for err in errors:
            results.append(InstallResult(component="wheels", success=False, message=err))
        return results

    # Install all wheels from the offline cache
    ok, out = _run(
        [
            "pip",
            "install",
            "--no-index",
            "--find-links",
            str(wheels_dir),
            *[e.package for e in manifest.wheels],
        ],
        runner=runner,
    )
    results.append(
        InstallResult(
            component="wheels",
            success=ok,
            message=out if ok else f"pip install failed: {out}",
        )
    )
    return results


def install_from_bundle(
    bundle_dir: Path,
    *,
    skip_docker: bool = False,
    skip_wheels: bool = False,
    runner=None,
) -> list[InstallResult]:
    """
    Full install from bundle. Reads manifest.json and installs each component.
    Returns all install results in order.
    """
    manifest = load_manifest(bundle_dir)
    results: list[InstallResult] = []

    file_errors = verify_file_checksums(manifest, bundle_dir)
    if file_errors:
        return [
            InstallResult(component="manifest", success=False, message=err) for err in file_errors
        ]

    if not skip_docker:
        results.extend(load_docker_images(manifest, bundle_dir, runner=runner))

    if not skip_wheels:
        results.extend(install_wheels(manifest, bundle_dir, runner=runner))

    return results
