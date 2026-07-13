"""Manifest CLI reports every integrity problem before exiting."""

from click.testing import CliRunner

from kit.bundle.manifest import BundleManifest, WheelEntry, save_manifest, sha256_file
from kit.cli import cli


def test_manifest_check_reports_file_and_wheel_errors(tmp_path):
    docker = tmp_path / "docker"
    wheels = tmp_path / "wheels"
    docker.mkdir()
    wheels.mkdir()
    image = docker / "image.tar"
    wheel = wheels / "demo-1.0.0-py3-none-any.whl"
    image.write_bytes(b"original image")
    wheel.write_bytes(b"original wheel")
    manifest = BundleManifest(
        "1.0.0",
        "2026-01-01T00:00:00Z",
        "arm64",
        wheels=[WheelEntry("demo==1.0.0", wheel.name, sha256_file(wheel))],
    )
    save_manifest(manifest, tmp_path)
    image.write_bytes(b"changed image")
    wheel.write_bytes(b"changed wheel")

    result = CliRunner().invoke(cli, ["manifest", "--check", "--bundle-dir", str(tmp_path)])

    assert result.exit_code == 1
    assert "image.tar" in result.output
    assert wheel.name in result.output
