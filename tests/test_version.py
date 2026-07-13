"""Keep package, CLI and project metadata versions aligned."""

from click.testing import CliRunner

from kit import __version__
from kit.cli import KIT_VERSION, cli


def test_version_consistency():
    result = CliRunner().invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == f"kit, version {__version__}"
    assert KIT_VERSION == __version__
