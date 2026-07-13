"""Tests for Docker and wheel bundlers using subprocess mocking."""

import tempfile
from pathlib import Path

from kit.bundle.docker_bundler import bundle_images, get_image_digest
from kit.bundle.manifest import sha256_file
from kit.bundle.wheel_bundler import download_wheels

# ---------------------------------------------------------------------------
# Fake subprocess runner
# ---------------------------------------------------------------------------


class FakeRunner:
    """
    Minimal fake subprocess runner for bundler tests.
    Records commands received; returns configurable outputs.
    """

    def __init__(self, outputs: dict | None = None):
        self.calls: list[list[str]] = []
        self._outputs = outputs or {}

    def __call__(self, cmd: list[str]) -> str:
        self.calls.append(cmd)
        key = " ".join(cmd[:3])  # match on first 3 tokens
        return self._outputs.get(key, "")


# ---------------------------------------------------------------------------
# Docker bundler tests
# ---------------------------------------------------------------------------


def test_get_image_digest_calls_docker_inspect():
    runner = FakeRunner(outputs={"docker inspect --format={{.Id}}": "sha256:deadbeef"})
    digest = get_image_digest("acme:latest", runner=runner)
    assert digest == "sha256:deadbeef"
    assert runner.calls[0] == [
        "docker",
        "inspect",
        "--format={{.Id}}",
        "acme:latest",
    ]


def test_bundle_images_creates_entries():
    with tempfile.TemporaryDirectory() as tmp:
        bundle_dir = Path(tmp)

        call_log: list[list[str]] = []

        def fake_runner(cmd: list[str]) -> str:
            call_log.append(cmd)
            if "inspect" in cmd:
                return "sha256:abc123"
            # docker save — create the tar file so bundle_images can record it
            # Find -o argument and create an empty file there
            if "save" in cmd:
                idx = cmd.index("-o")
                Path(cmd[idx + 1]).write_bytes(b"")
            return ""

        entries = bundle_images(["acme-parts-cloud:latest"], bundle_dir, runner=fake_runner)

        assert len(entries) == 1
        assert entries[0].image == "acme-parts-cloud:latest"
        assert entries[0].digest == "sha256:abc123"
        assert entries[0].filename == "acme-parts-cloud_latest.tar"
        # docker/acme-parts-cloud_latest.tar should exist
        assert (bundle_dir / "docker" / "acme-parts-cloud_latest.tar").exists()


# ---------------------------------------------------------------------------
# Wheel bundler tests
# ---------------------------------------------------------------------------


def test_download_wheels_returns_entries_for_existing_wheels():
    with tempfile.TemporaryDirectory() as tmp:
        bundle_dir = Path(tmp)
        wheels_dir = bundle_dir / "wheels"
        wheels_dir.mkdir()

        # Pre-populate wheels dir (simulating what pip download would create)
        whl = wheels_dir / "fde_data_forge-1.0.0-py3-none-any.whl"
        whl.write_bytes(b"fake whl content")

        call_log: list[list[str]] = []

        def fake_runner(cmd: list[str]) -> str:
            call_log.append(cmd)
            return ""

        entries = download_wheels(["fde-data-forge"], bundle_dir, runner=fake_runner)

        # pip download should have been called for the explicit package.
        assert any("pip" in cmd for cmd in call_log)
        assert "3.12" in call_log[0]
        # Entry should reflect the pre-existing wheel
        assert len(entries) == 1
        assert entries[0].filename == "fde_data_forge-1.0.0-py3-none-any.whl"
        assert len(entries[0].sha256) == 64  # hex SHA-256


def test_download_wheels_records_checksum():
    with tempfile.TemporaryDirectory() as tmp:
        bundle_dir = Path(tmp)
        wheels_dir = bundle_dir / "wheels"
        wheels_dir.mkdir()

        whl = wheels_dir / "mypackage-2.0.0-py3-none-any.whl"
        whl.write_bytes(b"deterministic content")
        expected_sha = sha256_file(whl)

        entries = download_wheels(["mypackage"], bundle_dir, runner=lambda cmd: "")

        assert entries[0].sha256 == expected_sha


def test_local_wheelhouse_is_copied_without_pip(tmp_path: Path):
    source = tmp_path / "wheelhouse"
    source.mkdir()
    wheel = source / "fde_data_forge-1.1.0-py3-none-any.whl"
    wheel.write_bytes(b"local wheel")
    bundle = tmp_path / "bundle"
    calls: list[list[str]] = []

    entries = download_wheels([], bundle, wheel_sources=[source], runner=calls.append)

    assert calls == []
    assert [entry.filename for entry in entries] == [wheel.name]
    assert (bundle / "wheels" / wheel.name).read_bytes() == b"local wheel"


def test_empty_local_wheelhouse_is_rejected(tmp_path: Path):
    import pytest

    source = tmp_path / "empty"
    source.mkdir()
    with pytest.raises(ValueError, match="No wheel files"):
        download_wheels([], tmp_path / "bundle", wheel_sources=[source])
