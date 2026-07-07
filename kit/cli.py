"""air-gap-deploy-kit CLI — bundle, deploy, and verify the acme-parts-cloud stack."""

from __future__ import annotations

import datetime
import platform
import sys
from pathlib import Path

import click
from rich.console import Console

from kit.bundle.docker_bundler import DEFAULT_IMAGES, bundle_images
from kit.bundle.manifest import (
    BundleManifest,
    load_manifest,
    save_manifest,
    verify_file_checksums,
    verify_wheel_checksums,
)
from kit.bundle.model_bundler import DEFAULT_MODELS, bundle_models
from kit.bundle.wheel_bundler import DEFAULT_PACKAGES, download_wheels
from kit.deploy.installer import install_from_bundle
from kit.deploy.verifier import verify_stack
from kit.report.builder import (
    print_install_results,
    print_manifest_summary,
    print_verify_results,
    save_report,
)

console = Console()

KIT_VERSION = "1.0.0"


@click.group()
def cli() -> None:
    """air-gap-deploy-kit: offline deployment for the acme-parts-cloud stack."""


# ---------------------------------------------------------------------------
# kit bundle
# ---------------------------------------------------------------------------


@cli.command("bundle")
@click.option(
    "--output-dir",
    default="./kit-bundle",
    show_default=True,
    help="Directory to write the bundle into.",
)
@click.option(
    "--images",
    multiple=True,
    default=DEFAULT_IMAGES,
    show_default=True,
    help="Docker images to bundle (repeatable).",
)
@click.option(
    "--packages",
    multiple=True,
    default=DEFAULT_PACKAGES,
    show_default=True,
    help="Python packages to bundle (repeatable).",
)
@click.option(
    "--models",
    multiple=True,
    default=DEFAULT_MODELS,
    show_default=True,
    help="Ollama models to bundle (repeatable).",
)
@click.option("--skip-docker", is_flag=True, default=False, help="Skip Docker image bundling.")
@click.option("--skip-wheels", is_flag=True, default=False, help="Skip Python wheel bundling.")
@click.option("--skip-models", is_flag=True, default=False, help="Skip Ollama model bundling.")
def bundle_cmd(
    output_dir: str,
    images: tuple[str, ...],
    packages: tuple[str, ...],
    models: tuple[str, ...],
    skip_docker: bool,
    skip_wheels: bool,
    skip_models: bool,
) -> None:
    """Bundle Docker images, Python wheels, and Ollama models for offline transfer."""
    bundle_dir = Path(output_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[bold cyan]air-gap-deploy-kit v{KIT_VERSION} — bundle[/bold cyan]")
    console.print(f"Output: {bundle_dir.resolve()}\n")

    manifest = BundleManifest(
        kit_version=KIT_VERSION,
        created_at=datetime.datetime.utcnow().isoformat() + "Z",
        platform=platform.machine(),
    )

    if not skip_docker:
        console.print("[cyan]→ Bundling Docker images…[/cyan]")
        try:
            manifest.docker = bundle_images(list(images), bundle_dir)
            console.print(f"  [green]✓[/green] {len(manifest.docker)} image(s) saved")
        except Exception as exc:
            console.print(f"  [red]✗ Docker bundling failed: {exc}[/red]")
            sys.exit(1)

    if not skip_wheels:
        console.print("[cyan]→ Downloading Python wheels…[/cyan]")
        try:
            manifest.wheels = download_wheels(list(packages), bundle_dir)
            console.print(f"  [green]✓[/green] {len(manifest.wheels)} wheel(s) downloaded")
        except Exception as exc:
            console.print(f"  [red]✗ Wheel download failed: {exc}[/red]")
            sys.exit(1)

    if not skip_models:
        console.print("[cyan]→ Bundling Ollama models…[/cyan]")
        manifest.models = bundle_models(list(models), bundle_dir)
        available = [m for m in manifest.models if m.manifest_digest != "unavailable"]
        skipped = [m for m in manifest.models if m.manifest_digest == "unavailable"]
        if available:
            console.print(f"  [green]✓[/green] {len(available)} model(s) copied")
        if skipped:
            console.print(
                f"  [yellow]⚠[/yellow] {len(skipped)} model(s) skipped "
                "(Ollama not running or model not pulled)"
            )

    path = save_manifest(manifest, bundle_dir)
    console.print(f"\n[green]✓ Bundle ready:[/green] {bundle_dir.resolve()}")
    console.print(f"  manifest.json → {path}")
    print_manifest_summary(manifest)


# ---------------------------------------------------------------------------
# kit deploy
# ---------------------------------------------------------------------------


@cli.command("deploy")
@click.option(
    "--bundle-dir",
    default="./kit-bundle",
    show_default=True,
    help="Path to the kit bundle directory.",
)
@click.option("--skip-docker", is_flag=True, default=False, help="Skip Docker image loading.")
@click.option("--skip-wheels", is_flag=True, default=False, help="Skip Python wheel installation.")
@click.option("--report", "report_path", default=None, help="Save JSON report to file.")
def deploy_cmd(
    bundle_dir: str, skip_docker: bool, skip_wheels: bool, report_path: str | None
) -> None:
    """Install from a local bundle — no internet required."""
    bundle_path = Path(bundle_dir)
    console.print(f"\n[bold cyan]air-gap-deploy-kit v{KIT_VERSION} — deploy[/bold cyan]")
    console.print(f"Bundle: {bundle_path.resolve()}\n")

    if not (bundle_path / "manifest.json").exists():
        console.print(f"[red]✗ No manifest.json found in {bundle_path}[/red]")
        sys.exit(1)

    manifest = load_manifest(bundle_path)
    print_manifest_summary(manifest)

    results = install_from_bundle(
        bundle_path,
        skip_docker=skip_docker,
        skip_wheels=skip_wheels,
    )
    print_install_results(results)

    if report_path:
        save_report(manifest, results, [], Path(report_path))

    failed = [r for r in results if not r.success]
    if failed:
        sys.exit(1)


# ---------------------------------------------------------------------------
# kit verify
# ---------------------------------------------------------------------------


@cli.command("verify")
@click.option(
    "--acme-url",
    default="http://localhost:8000",
    show_default=True,
    help="acme-parts-cloud base URL.",
)
@click.option(
    "--ollama-url",
    default="http://localhost:11434",
    show_default=True,
    help="Ollama base URL.",
)
@click.option(
    "--ollama-model",
    default="gemma:2b",
    show_default=True,
    help="Ollama model to check for.",
)
@click.option("--report", "report_path", default=None, help="Save JSON report to file.")
def verify_cmd(acme_url: str, ollama_url: str, ollama_model: str, report_path: str | None) -> None:
    """Smoke-test each stack component after deployment."""
    console.print(f"\n[bold cyan]air-gap-deploy-kit v{KIT_VERSION} — verify[/bold cyan]\n")

    results = verify_stack(
        acme_url=acme_url,
        ollama_url=ollama_url,
        ollama_model=ollama_model,
    )
    print_verify_results(results)

    if report_path:
        save_report(None, [], results, Path(report_path))

    failed = [r for r in results if not r.ok]
    if failed:
        # Ollama failure is a warning, not a fatal error (it's optional)
        ollama_only = all(r.component == "ollama" for r in failed)
        if ollama_only:
            console.print(
                "[yellow]⚠ Ollama check failed — generation scoring unavailable.[/yellow]"
            )
        else:
            sys.exit(1)


# ---------------------------------------------------------------------------
# kit manifest
# ---------------------------------------------------------------------------


@cli.command("manifest")
@click.option(
    "--bundle-dir",
    default="./kit-bundle",
    show_default=True,
    help="Path to the kit bundle directory.",
)
@click.option("--check", is_flag=True, help="Verify recorded bundle checksums.")
def manifest_cmd(bundle_dir: str, check: bool) -> None:
    """Display the manifest for an existing bundle."""
    bundle_path = Path(bundle_dir)
    if not (bundle_path / "manifest.json").exists():
        console.print(f"[red]✗ No manifest.json in {bundle_path}[/red]")
        sys.exit(1)
    manifest = load_manifest(bundle_path)
    print_manifest_summary(manifest)
    if check:
        errors = verify_file_checksums(manifest, bundle_path) or verify_wheel_checksums(
            manifest, bundle_path
        )
        if errors:
            console.print("[red]✗ Manifest check failed:[/red]")
            for err in errors:
                console.print(f"  [red]-[/red] {err}")
            sys.exit(1)
        console.print("[green]✓ Manifest check passed.[/green]")


if __name__ == "__main__":
    cli()
