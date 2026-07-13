"""Tests for a self-contained, component-aware bundle."""

import json
import subprocess

from click.testing import CliRunner

from kit.bundle.manifest import BundleManifest, save_manifest, verify_file_checksums
from kit.cli import cli
from kit.report.install_doc import render_install_doc


def _kit_wheelhouse(tmp_path):
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    (wheelhouse / "air_gap_deploy_kit-1.0.0-py3-none-any.whl").write_bytes(b"kit")
    return wheelhouse


def test_bundle_contains_standalone_verifier_and_install_guide(tmp_path):
    bundle = tmp_path / "bundle"
    result = CliRunner().invoke(
        cli,
        [
            "bundle",
            "--output-dir",
            str(bundle),
            "--wheel-source",
            str(_kit_wheelhouse(tmp_path)),
            "--skip-docker",
            "--skip-models",
        ],
    )
    assert result.exit_code == 0, result.output
    manifest = json.loads((bundle / "manifest.json").read_text())
    assert "VERIFY_BUNDLE.py" in manifest["file_checksums"]
    assert "INSTALL_OFFLINE.md" in manifest["file_checksums"]
    assert "read_bytes" not in (bundle / "VERIFY_BUNDLE.py").read_text()
    verified = subprocess.run(
        ["python3", str(bundle / "VERIFY_BUNDLE.py")], capture_output=True, text=True
    )
    assert verified.returncode == 0, verified.stdout + verified.stderr


def test_bundle_rejects_missing_bootstrap_kit_wheel(tmp_path):
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    (wheelhouse / "demo-1.0.0-py3-none-any.whl").write_bytes(b"demo")
    result = CliRunner().invoke(
        cli,
        [
            "bundle",
            "--output-dir",
            str(tmp_path / "bundle"),
            "--wheel-source",
            str(wheelhouse),
            "--skip-docker",
            "--skip-models",
        ],
    )
    assert result.exit_code == 1
    assert "must include air-gap-deploy-kit" in result.output


def test_ollama_export_is_rejected_instead_of_creating_broken_bundle(tmp_path):
    result = CliRunner().invoke(
        cli,
        ["bundle", "--output-dir", str(tmp_path / "bundle"), "--models", "gemma3:4b"],
    )
    assert result.exit_code == 1
    assert "cannot produce a restorable model" in result.output
    assert not (tmp_path / "bundle").exists()


def test_compose_is_included_only_when_explicit(tmp_path):
    compose = tmp_path / "compose.yml"
    compose.write_text("services: {}\n")
    bundle = tmp_path / "bundle"
    result = CliRunner().invoke(
        cli,
        [
            "bundle",
            "--output-dir",
            str(bundle),
            "--wheel-source",
            str(_kit_wheelhouse(tmp_path)),
            "--compose-file",
            str(compose),
            "--skip-docker",
            "--skip-models",
        ],
    )
    assert result.exit_code == 0, result.output
    manifest = json.loads((bundle / "manifest.json").read_text())
    assert manifest["compose_file"] == "docker-compose.yml"
    assert "docker-compose.yml" in manifest["file_checksums"]


def test_install_guide_is_component_aware():
    manifest = BundleManifest("1.0.0", "2026-01-01T00:00:00Z", "arm64")
    guide = render_install_doc(manifest)
    assert "docker compose" not in guide
    assert "Ollama" not in guide
    assert "do not authenticate" in guide


def test_manifest_check_rejects_unexpected_files(tmp_path):
    manifest = BundleManifest("1.0.0", "2026-01-01T00:00:00Z", "arm64")
    (tmp_path / "expected.txt").write_text("expected")
    save_manifest(manifest, tmp_path)
    (tmp_path / "injected.sh").write_text("echo injected")
    assert verify_file_checksums(manifest, tmp_path) == ["Unexpected bundle file: injected.sh"]
