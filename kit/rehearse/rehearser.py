"""Rehearse wheel installation in a network-isolated throwaway container."""

from __future__ import annotations

import shlex
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from kit.bundle.manifest import (
    BundleManifest,
    load_manifest,
    verify_file_checksums,
    verify_wheel_checksums,
)

DEFAULT_IMAGE = "python:3.12-slim"
KNOWN_CLIS = {
    "air-gap-deploy-kit": ["kit", "--help"],
    "fde-data-forge": ["fde", "--help"],
    "rag-eval-bench": ["rag-eval", "--help"],
}

_MANIFEST_CHECK_CODE = (
    "import sys; sys.path.insert(0, '/opt/kit-src'); "
    "from pathlib import Path; "
    "from kit.bundle.manifest import load_manifest, verify_file_checksums, verify_wheel_checksums; "
    "bundle=Path('/bundle'); manifest=load_manifest(bundle); "
    "errors=verify_file_checksums(manifest,bundle)+verify_wheel_checksums(manifest,bundle); "
    "print('\\n'.join(errors)); sys.exit(1 if errors else 0)"
)


@dataclass
class RehearseResult:
    step: str
    success: bool
    detail: str


def _run(cmd: list[str], *, runner=None) -> tuple[bool, str]:
    if runner is not None:
        try:
            return True, runner(cmd)
        except Exception as exc:
            return False, str(exc)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True, result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        output = getattr(exc, "stderr", None) or getattr(exc, "stdout", None) or str(exc)
        return False, str(output).strip()


def _smoke_commands(manifest: BundleManifest, smoke: tuple[str, ...]):
    if smoke:
        return [(value, shlex.split(value)) for value in smoke]
    commands = []
    for entry in manifest.wheels:
        package = entry.package.split("==", 1)[0].replace("_", "-").lower()
        if package in KNOWN_CLIS:
            command = KNOWN_CLIS[package]
            commands.append((" ".join(command), command))
    return commands


def _load_docker_tars(manifest: BundleManifest, bundle_dir: Path, *, runner=None):
    results = []
    for entry in manifest.docker:
        tar = bundle_dir / "docker" / entry.filename
        ok, output = _run(["docker", "load", "-i", str(tar)], runner=runner)
        if not ok:
            results.append(RehearseResult(f"docker load: {entry.image}", False, output))
            return results
        verified, digest = _run(
            ["docker", "inspect", "--format={{.Id}}", entry.image], runner=runner
        )
        matches = verified and digest.strip() == entry.digest.strip()
        results.append(
            RehearseResult(
                f"docker load: {entry.image}",
                matches,
                "loaded and image ID verified"
                if matches
                else f"post-load image ID mismatch: {digest.strip()}",
            )
        )
        if not matches:
            return results
    return results


def rehearse_bundle(
    bundle_dir: Path,
    *,
    image: str = DEFAULT_IMAGE,
    smoke: tuple[str, ...] = (),
    load_docker: bool = False,
    runner=None,
) -> list[RehearseResult]:
    """Fail-closed rehearsal with no image pulls and optional host Docker loading."""
    manifest = load_manifest(bundle_dir)
    integrity_errors = verify_file_checksums(manifest, bundle_dir) + verify_wheel_checksums(
        manifest, bundle_dir
    )
    if integrity_errors:
        return [RehearseResult("host integrity preflight", False, "; ".join(integrity_errors))]

    results = [RehearseResult("host integrity preflight", True, "all bundle files verified")]
    name = f"kit-rehearse-{uuid.uuid4().hex[:8]}"
    kit_src = Path(__file__).resolve().parents[1]
    ok, output = _run(
        [
            "docker",
            "run",
            "--pull=never",
            "-d",
            "--name",
            name,
            "--network",
            "none",
            "-v",
            f"{bundle_dir.resolve()}:/bundle:ro",
            "-v",
            f"{kit_src}:/opt/kit-src/kit:ro",
            image,
            "sleep",
            "infinity",
        ],
        runner=runner,
    )
    results.append(RehearseResult("container (--pull=never, --network none)", ok, output))
    if not ok:
        return results

    try:
        ok, output = _run(
            ["docker", "exec", name, "python", "-c", _MANIFEST_CHECK_CODE], runner=runner
        )
        results.append(RehearseResult("container integrity check", ok, output or "verified"))
        if not ok:
            return results

        packages = [entry.package for entry in manifest.wheels]
        ok, output = _run(
            [
                "docker",
                "exec",
                name,
                "python",
                "-m",
                "pip",
                "install",
                "--no-index",
                "--find-links",
                "/bundle/wheels",
                *packages,
            ],
            runner=runner,
        )
        results.append(RehearseResult("wheel install (--no-index)", ok, output or "installed"))
        if not ok:
            return results

        for label, command in _smoke_commands(manifest, smoke):
            ok, output = _run(["docker", "exec", name, *command], runner=runner)
            results.append(RehearseResult(f"smoke: {label}", ok, output or "exit 0"))
            if not ok:
                return results
    finally:
        removed, output = _run(["docker", "rm", "-f", name], runner=runner)
        if not removed:
            results.append(RehearseResult("container cleanup", False, output))

    if any(not result.success for result in results):
        return results

    if manifest.docker:
        if load_docker:
            results.extend(_load_docker_tars(manifest, bundle_dir, runner=runner))
        else:
            results.append(
                RehearseResult(
                    "host Docker load",
                    True,
                    "skipped; pass --load-docker to opt into host mutation",
                )
            )
    return results
