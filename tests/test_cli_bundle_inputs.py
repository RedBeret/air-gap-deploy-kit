"""CLI tests for explicit, real bundle inputs."""

from click.testing import CliRunner

from kit.cli import cli


def test_bundle_rejects_empty_default_input(tmp_path):
    result = CliRunner().invoke(cli, ["bundle", "--output-dir", str(tmp_path / "bundle")])
    assert result.exit_code == 1
    assert "No bundle inputs selected" in result.output
    assert not (tmp_path / "bundle").exists()


def test_bundle_accepts_local_wheelhouse(tmp_path):
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    wheel = wheelhouse / "air_gap_deploy_kit-1.0.0-py3-none-any.whl"
    wheel.write_bytes(b"wheel")

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

    assert result.exit_code == 0, result.output
    assert (tmp_path / "bundle" / "wheels" / wheel.name).exists()
    assert (tmp_path / "bundle" / "manifest.json").exists()
