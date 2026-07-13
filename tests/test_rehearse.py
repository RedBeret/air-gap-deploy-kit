"""Fail-closed offline rehearsal tests with an injected Docker runner."""

from kit.bundle.manifest import BundleManifest, DockerEntry, WheelEntry, save_manifest, sha256_file
from kit.rehearse.rehearser import rehearse_bundle


class Runner:
    def __init__(self, failures=()):
        self.calls = []
        self.failures = failures

    def __call__(self, command):
        self.calls.append(command)
        joined = " ".join(command)
        if any(value in joined for value in self.failures):
            raise RuntimeError(f"failed: {joined}")
        if command[:2] == ["docker", "run"]:
            return "container-id"
        if command[:2] == ["docker", "inspect"]:
            return "sha256:image"
        return ""


def _bundle(tmp_path, with_docker=False):
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    wheel = wheels / "air_gap_deploy_kit-1.0.0-py3-none-any.whl"
    wheel.write_bytes(b"wheel")
    manifest = BundleManifest(
        "1.0.0",
        "2026-01-01T00:00:00Z",
        "arm64",
        wheels=[WheelEntry("air-gap-deploy-kit==1.0.0", wheel.name, sha256_file(wheel))],
    )
    if with_docker:
        docker = tmp_path / "docker"
        docker.mkdir()
        (docker / "image.tar").write_bytes(b"image")
        manifest.docker = [DockerEntry("demo:latest", "sha256:image", "image.tar")]
    save_manifest(manifest, tmp_path)
    return wheel


def test_rehearsal_disables_pulls_and_network(tmp_path):
    _bundle(tmp_path)
    runner = Runner()
    results = rehearse_bundle(tmp_path, runner=runner)
    command = next(call for call in runner.calls if call[:2] == ["docker", "run"])
    assert "--pull=never" in command
    assert command[command.index("--network") + 1] == "none"
    assert all(result.success for result in results)


def test_integrity_failure_executes_nothing(tmp_path):
    wheel = _bundle(tmp_path)
    wheel.write_bytes(b"corrupt")
    runner = Runner()
    results = rehearse_bundle(tmp_path, runner=runner)
    assert not results[0].success
    assert runner.calls == []


def test_failed_install_skips_smoke_and_host_load(tmp_path):
    _bundle(tmp_path, with_docker=True)
    runner = Runner(failures=("pip install",))
    results = rehearse_bundle(tmp_path, load_docker=True, runner=runner)
    assert any(
        result.step == "wheel install (--no-index)" and not result.success for result in results
    )
    assert not any("--help" in call for call in runner.calls)
    assert not any(call[:2] == ["docker", "load"] for call in runner.calls)


def test_host_docker_load_is_opt_in(tmp_path):
    _bundle(tmp_path, with_docker=True)
    runner = Runner()
    results = rehearse_bundle(tmp_path, runner=runner)
    assert not any(call[:2] == ["docker", "load"] for call in runner.calls)
    assert any("skipped" in result.detail for result in results)


def test_opt_in_docker_load_verifies_image_id(tmp_path):
    _bundle(tmp_path, with_docker=True)
    runner = Runner()
    results = rehearse_bundle(tmp_path, load_docker=True, runner=runner)
    assert any(call[:2] == ["docker", "load"] for call in runner.calls)
    assert results[-1].success
    assert "image ID verified" in results[-1].detail


def test_cleanup_failure_fails_rehearsal(tmp_path):
    _bundle(tmp_path, with_docker=True)
    runner = Runner(failures=("docker rm",))
    results = rehearse_bundle(tmp_path, load_docker=True, runner=runner)
    assert results[-1].step == "container cleanup"
    assert not results[-1].success
    assert not any(call[:2] == ["docker", "load"] for call in runner.calls)
