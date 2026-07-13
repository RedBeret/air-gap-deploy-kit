"""Write the dependency-free transfer verifier shipped in every bundle."""

from pathlib import Path

VERIFY_SCRIPT_NAME = "VERIFY_BUNDLE.py"

VERIFY_SCRIPT = '''#!/usr/bin/env python3
"""Verify transfer integrity before installing or executing bundle content."""
import hashlib
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
expected = manifest.get("file_checksums", {})
actual_files = {
    path.relative_to(root).as_posix()
    for path in root.rglob("*")
    if path.is_file() and path.name != "manifest.json"
}
errors = []
def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
for relative, digest in expected.items():
    path = root / relative
    if not path.is_file():
        errors.append(f"missing: {relative}")
        continue
    actual = sha256_file(path)
    if actual != digest:
        errors.append(f"checksum mismatch: {relative}")
for relative in sorted(actual_files - set(expected)):
    errors.append(f"unexpected file: {relative}")
if errors:
    print("Bundle verification failed:")
    print("\\n".join(f"- {error}" for error in errors))
    sys.exit(1)
print("Bundle transfer verification passed.")
'''


def write_bootstrap_verifier(bundle_dir: Path) -> Path:
    """Write the standalone verifier before manifest checksums are calculated."""
    path = bundle_dir / VERIFY_SCRIPT_NAME
    path.write_text(VERIFY_SCRIPT, encoding="utf-8")
    return path
