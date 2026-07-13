"""Live rehearsal using only a Docker image already present on the host."""

import base64
import hashlib
import shutil
import subprocess
import zipfile

import pytest

from kit.bundle.manifest import BundleManifest, WheelEntry, save_manifest, sha256_file
from kit.rehearse.rehearser import DEFAULT_IMAGE, rehearse_bundle

pytestmark = pytest.mark.docker


def _image_is_local():
    if shutil.which("docker") is None:
        return False
    return (
        subprocess.run(
            ["docker", "image", "inspect", DEFAULT_IMAGE], capture_output=True, timeout=15
        ).returncode
        == 0
    )


def _tiny_wheel(directory):
    name, version = "tinypkg", "0.1.0"
    info = f"{name}-{version}.dist-info"
    files = {
        f"{name}/__init__.py": b'def main():\n    print("tiny ok")\n',
        f"{info}/METADATA": f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n".encode(),
        f"{info}/WHEEL": b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        f"{info}/entry_points.txt": b"[console_scripts]\ntiny = tinypkg:main\n",
    }
    records = []
    for path, data in files.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        records.append(f"{path},sha256={digest},{len(data)}")
    records.append(f"{info}/RECORD,,")
    files[f"{info}/RECORD"] = ("\n".join(records) + "\n").encode()
    wheel = directory / f"{name}-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, data in files.items():
            archive.writestr(path, data)
    return wheel


@pytest.mark.skipif(not _image_is_local(), reason=f"{DEFAULT_IMAGE} is not preloaded")
def test_live_rehearsal_never_pulls_or_uses_container_network(tmp_path):
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    wheel = _tiny_wheel(wheels)
    manifest = BundleManifest(
        "1.0.0",
        "2026-01-01T00:00:00Z",
        "arm64",
        wheels=[WheelEntry("tinypkg==0.1.0", wheel.name, sha256_file(wheel))],
    )
    save_manifest(manifest, tmp_path)

    results = rehearse_bundle(tmp_path, smoke=("tiny",))

    assert all(result.success for result in results), results
    assert any(result.step == "smoke: tiny" and "tiny ok" in result.detail for result in results)
