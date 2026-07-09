"""Bundle manifest — records what was collected and validates integrity on the target."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class DockerEntry:
    image: str  # e.g. "acme-parts-cloud:v1.0.0"
    digest: str  # image ID from `docker inspect --format={{.Id}}`
    filename: str  # relative path inside bundle/docker/


@dataclass
class WheelEntry:
    package: str  # e.g. "fde-data-forge==1.0.0"
    filename: str  # relative path inside bundle/wheels/
    sha256: str  # hex digest of the .whl file


@dataclass
class ModelEntry:
    name: str  # e.g. "gemma:2b"
    provider: str  # "ollama"
    manifest_digest: str  # digest from Ollama registry
    blob_files: list[str] = field(default_factory=list)  # relative paths in bundle/models/


@dataclass
class BundleManifest:
    kit_version: str
    created_at: str
    platform: str  # e.g. "linux/amd64"
    docker: list[DockerEntry] = field(default_factory=list)
    wheels: list[WheelEntry] = field(default_factory=list)
    models: list[ModelEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "kit_version": self.kit_version,
            "created_at": self.created_at,
            "platform": self.platform,
            "docker": [
                {"image": e.image, "digest": e.digest, "filename": e.filename} for e in self.docker
            ],
            "wheels": [
                {"package": e.package, "filename": e.filename, "sha256": e.sha256}
                for e in self.wheels
            ],
            "models": [
                {
                    "name": e.name,
                    "provider": e.provider,
                    "manifest_digest": e.manifest_digest,
                    "blob_files": e.blob_files,
                }
                for e in self.models
            ],
        }

    @classmethod
    def from_dict(cls, d: dict) -> BundleManifest:
        return cls(
            kit_version=d["kit_version"],
            created_at=d["created_at"],
            platform=d["platform"],
            docker=[
                DockerEntry(image=e["image"], digest=e["digest"], filename=e["filename"])
                for e in d.get("docker", [])
            ],
            wheels=[
                WheelEntry(package=e["package"], filename=e["filename"], sha256=e["sha256"])
                for e in d.get("wheels", [])
            ],
            models=[
                ModelEntry(
                    name=e["name"],
                    provider=e["provider"],
                    manifest_digest=e["manifest_digest"],
                    blob_files=e.get("blob_files", []),
                )
                for e in d.get("models", [])
            ],
        )


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def save_manifest(manifest: BundleManifest, bundle_dir: Path) -> Path:
    """Write manifest.json to bundle_dir root. Returns the path written."""
    path = bundle_dir / "manifest.json"
    path.write_text(json.dumps(manifest.to_dict(), indent=2))
    return path


def load_manifest(bundle_dir: Path) -> BundleManifest:
    """Load manifest.json from bundle_dir root."""
    path = bundle_dir / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"No manifest.json in {bundle_dir}")
    return BundleManifest.from_dict(json.loads(path.read_text()))


# ---------------------------------------------------------------------------
# Integrity helpers
# ---------------------------------------------------------------------------


def sha256_file(path: Path, chunk_size: int = 65536) -> str:
    """Return hex SHA-256 digest for a file."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def verify_wheel_checksums(manifest: BundleManifest, bundle_dir: Path) -> list[str]:
    """
    Check that every wheel file in the manifest still matches its recorded SHA-256.
    Returns a list of error strings (empty = all good).
    """
    errors: list[str] = []
    wheels_dir = bundle_dir / "wheels"
    for entry in manifest.wheels:
        whl_path = wheels_dir / entry.filename
        if not whl_path.exists():
            errors.append(f"Missing wheel: {entry.filename}")
            continue
        actual = sha256_file(whl_path)
        if actual != entry.sha256:
            errors.append(
                f"Checksum mismatch for {entry.filename}: "
                f"expected {entry.sha256[:12]}… got {actual[:12]}…"
            )
    return errors
