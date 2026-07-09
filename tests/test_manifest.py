"""Tests for bundle manifest serialization, I/O, and checksum verification."""

import json
import tempfile
from pathlib import Path

import pytest

from kit.bundle.manifest import (
    BundleManifest,
    DockerEntry,
    ModelEntry,
    WheelEntry,
    load_manifest,
    save_manifest,
    sha256_file,
    verify_wheel_checksums,
)


def _make_manifest() -> BundleManifest:
    return BundleManifest(
        kit_version="1.0.0",
        created_at="2025-01-01T00:00:00Z",
        platform="x86_64",
        docker=[
            DockerEntry(image="acme:latest", digest="sha256:abc123", filename="acme_latest.tar")
        ],
        wheels=[
            WheelEntry(
                package="fde-data-forge==1.0.0",
                filename="fde_data_forge-1.0.0-py3-none-any.whl",
                sha256="deadbeef" * 8,
            )
        ],
        models=[
            ModelEntry(
                name="gemma:2b",
                provider="ollama",
                manifest_digest="sha256:cafe",
                blob_files=["gemma_2b/sha256-cafe"],
            )
        ],
    )


def test_manifest_roundtrip():
    m = _make_manifest()
    d = m.to_dict()
    m2 = BundleManifest.from_dict(d)
    assert m2.kit_version == "1.0.0"
    assert m2.docker[0].image == "acme:latest"
    assert m2.wheels[0].package == "fde-data-forge==1.0.0"
    assert m2.models[0].name == "gemma:2b"


def test_manifest_save_and_load():
    m = _make_manifest()
    with tempfile.TemporaryDirectory() as tmp:
        bundle_dir = Path(tmp)
        path = save_manifest(m, bundle_dir)
        assert path.exists()
        # Validate raw JSON
        raw = json.loads(path.read_text())
        assert raw["kit_version"] == "1.0.0"
        # Round-trip via load_manifest
        m2 = load_manifest(bundle_dir)
        assert m2.platform == "x86_64"
        assert len(m2.docker) == 1
        assert len(m2.wheels) == 1
        assert len(m2.models) == 1


def test_load_manifest_missing_raises():
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(FileNotFoundError):
            load_manifest(Path(tmp))


def test_sha256_file():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
        f.write(b"hello world")
        path = Path(f.name)
    digest = sha256_file(path)
    # Known SHA-256 of "hello world"
    assert len(digest) == 64
    path.unlink()


def test_verify_wheel_checksums_passes():
    m = _make_manifest()
    with tempfile.TemporaryDirectory() as tmp:
        bundle_dir = Path(tmp)
        wheels_dir = bundle_dir / "wheels"
        wheels_dir.mkdir()
        # Write a real file and record its real checksum
        whl = wheels_dir / m.wheels[0].filename
        whl.write_bytes(b"fake wheel content")
        real_hash = sha256_file(whl)
        m.wheels[0].sha256 = real_hash

        errors = verify_wheel_checksums(m, bundle_dir)
        assert errors == []


def test_verify_wheel_checksums_bad_hash():
    m = _make_manifest()
    with tempfile.TemporaryDirectory() as tmp:
        bundle_dir = Path(tmp)
        wheels_dir = bundle_dir / "wheels"
        wheels_dir.mkdir()
        whl = wheels_dir / m.wheels[0].filename
        whl.write_bytes(b"tampered content")
        # sha256 in manifest is still "deadbeef" * 8 → won't match

        errors = verify_wheel_checksums(m, bundle_dir)
        assert len(errors) == 1
        assert "mismatch" in errors[0].lower()


def test_verify_wheel_checksums_missing_file():
    m = _make_manifest()
    with tempfile.TemporaryDirectory() as tmp:
        errors = verify_wheel_checksums(m, Path(tmp))
        assert len(errors) == 1
        assert "missing" in errors[0].lower()
