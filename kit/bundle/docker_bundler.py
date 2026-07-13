"""Docker image bundler — saves images to .tar files for offline transfer."""

from __future__ import annotations

import subprocess
from pathlib import Path

from kit.bundle.manifest import DockerEntry

# Images are explicit inputs. A default tag that is not present locally makes
# an offline bundle command fail before it can produce anything useful.
DEFAULT_IMAGES: list[str] = []


def _run(cmd: list[str], *, runner=None) -> str:
    """
    Run a subprocess command and return stdout.
    If runner is provided, delegate to it (used in tests for mocking).
    """
    if runner is not None:
        return runner(cmd)
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def get_image_digest(image: str, *, runner=None) -> str:
    """Return the image ID (sha256) for a local image."""
    return _run(
        ["docker", "inspect", "--format={{.Id}}", image],
        runner=runner,
    )


def save_image(image: str, output_path: Path, *, runner=None) -> None:
    """Save a Docker image to a .tar file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if runner is not None:
        runner(["docker", "save", "-o", str(output_path), image])
        return
    subprocess.run(
        ["docker", "save", "-o", str(output_path), image],
        check=True,
        capture_output=True,
    )


def bundle_images(
    images: list[str],
    bundle_dir: Path,
    *,
    runner=None,
) -> list[DockerEntry]:
    """
    Save each image to bundle_dir/docker/<safe_name>.tar.
    Returns a list of DockerEntry records for the manifest.
    """
    docker_dir = bundle_dir / "docker"
    docker_dir.mkdir(parents=True, exist_ok=True)

    entries: list[DockerEntry] = []
    for image in images:
        # Sanitize image name for use as a filename
        safe = image.replace("/", "_").replace(":", "_").replace(".", "_")
        filename = f"{safe}.tar"
        tar_path = docker_dir / filename

        digest = get_image_digest(image, runner=runner)
        save_image(image, tar_path, runner=runner)

        entries.append(DockerEntry(image=image, digest=digest, filename=filename))

    return entries
