"""Ollama model bundler — copies model blobs for offline transfer."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import httpx

from kit.bundle.manifest import ModelEntry

# Default Ollama base URL
OLLAMA_BASE_URL = "http://localhost:11434"

# Default model (dogfooding rag-eval-bench Ollama integration)
DEFAULT_MODELS = ["gemma:2b"]


def _ollama_get(path: str, base_url: str = OLLAMA_BASE_URL, *, client=None) -> dict:
    """GET from Ollama API. Accepts an injected httpx client for tests."""
    if client is not None:
        resp = client.get(f"{base_url}{path}")
    else:
        resp = httpx.get(f"{base_url}{path}", timeout=10)
    resp.raise_for_status()
    return resp.json()


def is_ollama_available(base_url: str = OLLAMA_BASE_URL, *, client=None) -> bool:
    """Return True if Ollama is reachable."""
    try:
        _ollama_get("/api/tags", base_url, client=client)
        return True
    except Exception:
        return False


def get_model_manifest_digest(
    model: str, base_url: str = OLLAMA_BASE_URL, *, client=None
) -> str | None:
    """
    Return the manifest digest for a locally-pulled model, or None if not found.
    Uses GET /api/show which returns model metadata including the digest.
    """
    try:
        if client is not None:
            resp = client.post(f"{base_url}/api/show", json={"name": model})
        else:
            resp = httpx.post(
                f"{base_url}/api/show",
                json={"name": model},
                timeout=10,
            )
        resp.raise_for_status()
        data = resp.json()
        # digest is nested under model_info in newer Ollama versions
        return data.get("details", {}).get("parent_model") or data.get("digest", "unknown")
    except Exception:
        return None


def _find_ollama_blobs_dir() -> Path | None:
    """
    Locate the Ollama model blobs directory on the local filesystem.
    Standard locations: ~/.ollama/models/blobs (Linux/Mac) or
    %LOCALAPPDATA%\\Ollama\\models\\blobs (Windows).
    """
    candidates = [
        Path.home() / ".ollama" / "models" / "blobs",
        Path("/usr/share/ollama/.ollama/models/blobs"),
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def bundle_models(
    models: list[str],
    bundle_dir: Path,
    base_url: str = OLLAMA_BASE_URL,
    *,
    client=None,
    blobs_dir: Path | None = None,
) -> list[ModelEntry]:
    """
    Copy Ollama model blobs into bundle_dir/models/<model_name>/.
    Returns ModelEntry records for the manifest.

    If Ollama is not running or a model is not pulled, returns an entry with
    manifest_digest="unavailable" and no blob files — the deploy verifier will
    flag this as a warning rather than an error.
    """
    models_dir = bundle_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    if blobs_dir is None:
        blobs_dir = _find_ollama_blobs_dir()

    entries: list[ModelEntry] = []
    for model in models:
        digest = get_model_manifest_digest(model, base_url, client=client)

        if digest is None or blobs_dir is None:
            entries.append(
                ModelEntry(
                    name=model,
                    provider="ollama",
                    manifest_digest="unavailable",
                    blob_files=[],
                )
            )
            continue

        # Create per-model subdir in bundle
        safe_name = model.replace(":", "_").replace("/", "_")
        model_bundle_dir = models_dir / safe_name
        model_bundle_dir.mkdir(parents=True, exist_ok=True)

        # Copy all blobs (sha256:... files) for this model
        # Ollama stores blobs as sha256-{hex} files
        blob_files: list[str] = []
        for blob_path in blobs_dir.iterdir():
            if blob_path.is_file():
                dest = model_bundle_dir / blob_path.name
                if not dest.exists():
                    shutil.copy2(blob_path, dest)
                blob_files.append(f"{safe_name}/{blob_path.name}")

        entries.append(
            ModelEntry(
                name=model,
                provider="ollama",
                manifest_digest=digest,
                blob_files=blob_files,
            )
        )

    return entries


def sha256_file(path: Path, chunk_size: int = 65536) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()
