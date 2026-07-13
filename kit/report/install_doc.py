"""Render the component-aware offline install guide shipped in a bundle."""

from pathlib import Path

from kit.bundle.manifest import BundleManifest

INSTALL_DOC_NAME = "INSTALL_OFFLINE.md"


def render_install_doc(manifest: BundleManifest) -> str:
    """Render instructions that match only the components actually bundled."""
    lines = [
        "# Offline Install Guide",
        "",
        f"Built with air-gap-deploy-kit v{manifest.kit_version} on {manifest.created_at}.",
        "",
        "These checksums detect transfer corruption. They do not authenticate the bundle;",
        "compare its manifest digest through a separate trusted channel when authenticity matters.",
        "",
        "## Prerequisites",
        "",
        "- Python 3.12+ with pip",
    ]
    if manifest.docker:
        lines.append("- Docker Engine with the required rehearsal image already present")
    lines += [
        "",
        "## 1. Verify the transferred files before executing bundle content",
        "",
        "```bash",
        "python VERIFY_BUNDLE.py",
        "```",
        "",
        "Stop and re-transfer the bundle if this command fails.",
        "",
        "## 2. Bootstrap the kit from its bundled wheelhouse",
        "",
        "```bash",
        "python -m pip install --no-index --find-links wheels air-gap-deploy-kit",
        "kit manifest --check --bundle-dir .",
        "```",
        "",
        "## 3. Install bundled components",
        "",
        "```bash",
        "kit deploy --bundle-dir .",
        "```",
        "",
    ]
    if manifest.docker:
        lines += ["Docker images:", "", *[f"- `{entry.image}`" for entry in manifest.docker], ""]
    if manifest.wheels:
        lines += [f"Python wheelhouse: {len(manifest.wheels)} wheel(s).", ""]
    if manifest.compose_file:
        lines += [
            "## 4. Start the bundled Compose stack",
            "",
            "```bash",
            f"docker compose -f {manifest.compose_file} up -d",
            "```",
            "",
        ]
    lines += [
        "## Verify",
        "",
        "Run `kit verify` after the services you selected are started.",
        "",
    ]
    return "\n".join(lines)


def write_install_doc(manifest: BundleManifest, bundle_dir: Path) -> Path:
    path = bundle_dir / INSTALL_DOC_NAME
    path.write_text(render_install_doc(manifest), encoding="utf-8")
    return path
