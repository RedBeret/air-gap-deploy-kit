# Contributing to air-gap-deploy-kit

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
pip install ruff pytest pytest-httpx
```

## Run Tests

```bash
pytest -v
```

Tests mock all subprocess and HTTP calls — no Docker, pip download, or Ollama required.

## Lint

```bash
ruff check .
ruff format .
```

## Layout

```
kit/
  bundle/
    manifest.py       — BundleManifest dataclass + I/O + checksum helpers
    docker_bundler.py — docker save/inspect wrapper
    wheel_bundler.py  — local wheelhouse + explicit pip download wrapper
  deploy/
    installer.py      — docker load + pip install --no-index
    verifier.py       — smoke tests for each stack component
  report/
    bootstrap.py      — dependency-free transfer verifier generator
    install_doc.py    — component-aware offline guide generator
    builder.py        — rich terminal tables + JSON report
  rehearse/
    rehearser.py      — fail-closed network-isolated install rehearsal
  cli.py              — click entry point (kit command)
tests/
  test_manifest.py
  test_bundle.py
  test_verifier.py
  test_rehearse.py
  test_rehearse_docker.py
samples/
  bundle_manifest_sample.json
```

## Subprocess Mocking

Bundler and installer functions accept a `runner=` keyword argument.
Pass a callable `runner(cmd: list[str]) -> str` to replace `subprocess.run` in tests.
This keeps CI fast and side-effect-free.

## PR Workflow

1. Branch off `main`
2. `pytest -v` + `ruff check .` green before opening PR
3. No direct pushes to main
