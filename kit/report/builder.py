"""Rich terminal output for bundle, install, and verify results."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

from kit.bundle.manifest import BundleManifest
from kit.deploy.installer import InstallResult
from kit.deploy.verifier import VerifyResult

console = Console()


def print_manifest_summary(manifest: BundleManifest) -> None:
    """Print a summary table of what's in the bundle."""
    console.print("\n[bold cyan]Bundle Manifest[/bold cyan]")
    console.print(f"  Kit version : {manifest.kit_version}")
    console.print(f"  Created at  : {manifest.created_at}")
    console.print(f"  Platform    : {manifest.platform}")

    if manifest.docker:
        t = Table(title="Docker Images", show_lines=False)
        t.add_column("Image", style="cyan")
        t.add_column("Digest (short)")
        t.add_column("Tar file")
        for e in manifest.docker:
            short = e.digest[:19] + "…" if len(e.digest) > 20 else e.digest
            t.add_row(e.image, short, e.filename)
        console.print(t)

    if manifest.wheels:
        t = Table(title="Python Wheels", show_lines=False)
        t.add_column("Package", style="cyan")
        t.add_column("SHA-256 (short)")
        for e in manifest.wheels:
            t.add_row(e.package, e.sha256[:16] + "…")
        console.print(t)

    if manifest.models:
        t = Table(title="Ollama Models", show_lines=False)
        t.add_column("Model", style="cyan")
        t.add_column("Digest")
        t.add_column("Blobs")
        for e in manifest.models:
            t.add_row(e.name, e.manifest_digest[:20], str(len(e.blob_files)))
        console.print(t)


def print_install_results(results: list[InstallResult]) -> None:
    """Print install step outcomes."""
    console.print("\n[bold cyan]Install Results[/bold cyan]")
    t = Table(show_lines=False)
    t.add_column("Component", style="cyan")
    t.add_column("Status")
    t.add_column("Detail")
    for r in results:
        status = "[green]✓ OK[/green]" if r.success else "[red]✗ FAIL[/red]"
        t.add_row(r.component, status, r.message)
    console.print(t)

    failed = [r for r in results if not r.success]
    if failed:
        console.print(f"\n[red]✗ {len(failed)} step(s) failed.[/red]")
    else:
        console.print("\n[green]✓ All install steps succeeded.[/green]")


def print_verify_results(results: list[VerifyResult]) -> None:
    """Print verification check outcomes."""
    console.print("\n[bold cyan]Stack Verification[/bold cyan]")
    t = Table(show_lines=False)
    t.add_column("Component", style="cyan")
    t.add_column("Status")
    t.add_column("Detail")
    for r in results:
        status = "[green]✓ OK[/green]" if r.ok else "[red]✗ FAIL[/red]"
        t.add_row(r.component, status, r.detail)
    console.print(t)

    passed = sum(1 for r in results if r.ok)
    total = len(results)
    color = "green" if passed == total else "yellow" if passed > 0 else "red"
    console.print(f"\n[{color}]{passed}/{total} checks passed.[/{color}]")


def save_report(
    manifest: BundleManifest | None,
    install_results: list[InstallResult],
    verify_results: list[VerifyResult],
    output_path: Path,
) -> None:
    """Save a JSON report of the full deployment run."""
    report = {
        "manifest": manifest.to_dict() if manifest else None,
        "install": [
            {"component": r.component, "success": r.success, "message": r.message}
            for r in install_results
        ],
        "verify": [
            {"component": r.component, "ok": r.ok, "detail": r.detail} for r in verify_results
        ],
    }
    output_path.write_text(json.dumps(report, indent=2))
    console.print(f"\n[dim]Report saved → {output_path}[/dim]")
