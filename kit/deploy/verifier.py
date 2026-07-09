"""Deployment verifier — smoke-tests each stack component after install."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

import httpx


@dataclass
class VerifyResult:
    component: str
    ok: bool
    detail: str


# ---------------------------------------------------------------------------
# Individual component checks
# ---------------------------------------------------------------------------


def check_acme_api(
    base_url: str = "http://localhost:8000",
    *,
    client: httpx.Client | None = None,
) -> VerifyResult:
    """
    Ping acme-parts-cloud: GET /health.
    Returns ok if HTTP 200 with {"status": "ok"}.
    """
    try:
        if client is not None:
            resp = client.get(f"{base_url}/health", timeout=5)
        else:
            resp = httpx.get(f"{base_url}/health", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "ok":
            return VerifyResult("acme-parts-cloud", ok=True, detail="GET /health → 200 ok")
        return VerifyResult(
            "acme-parts-cloud",
            ok=False,
            detail=f"GET /health returned unexpected body: {data}",
        )
    except httpx.HTTPStatusError as exc:
        return VerifyResult(
            "acme-parts-cloud",
            ok=False,
            detail=f"HTTP {exc.response.status_code}: {exc.response.text[:120]}",
        )
    except Exception as exc:
        return VerifyResult("acme-parts-cloud", ok=False, detail=str(exc))


def check_fde_cli(*, runner=None) -> VerifyResult:
    """
    Verify fde-data-forge CLI is importable: `fde --help`.
    """
    try:
        if runner is not None:
            out = runner(["fde", "--help"])
            return VerifyResult("fde-data-forge", ok=True, detail=f"fde --help: {out[:60]}")
        result = subprocess.run(
            ["fde", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return VerifyResult(
                "fde-data-forge",
                ok=True,
                detail=f"fde --help exit 0: {result.stdout[:60].strip()}",
            )
        return VerifyResult(
            "fde-data-forge",
            ok=False,
            detail=f"fde --help exit {result.returncode}: {result.stderr[:120].strip()}",
        )
    except FileNotFoundError:
        return VerifyResult("fde-data-forge", ok=False, detail="fde CLI not found — not installed?")
    except Exception as exc:
        return VerifyResult("fde-data-forge", ok=False, detail=str(exc))


def check_rag_cli(*, runner=None) -> VerifyResult:
    """
    Verify rag-eval-bench CLI is importable: `rag-eval --help`.
    """
    try:
        if runner is not None:
            out = runner(["rag-eval", "--help"])
            return VerifyResult("rag-eval-bench", ok=True, detail=f"rag-eval --help: {out[:60]}")
        result = subprocess.run(
            ["rag-eval", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return VerifyResult(
                "rag-eval-bench",
                ok=True,
                detail=f"rag-eval --help exit 0: {result.stdout[:60].strip()}",
            )
        return VerifyResult(
            "rag-eval-bench",
            ok=False,
            detail=f"rag-eval --help exit {result.returncode}: {result.stderr[:120].strip()}",
        )
    except FileNotFoundError:
        return VerifyResult(
            "rag-eval-bench", ok=False, detail="rag-eval CLI not found — not installed?"
        )
    except Exception as exc:
        return VerifyResult("rag-eval-bench", ok=False, detail=str(exc))


def check_ollama(
    base_url: str = "http://localhost:11434",
    model: str = "gemma:2b",
    *,
    client: httpx.Client | None = None,
) -> VerifyResult:
    """
    Check Ollama is running and the required model is available.
    Uses GET /api/tags to list pulled models.
    """
    try:
        if client is not None:
            resp = client.get(f"{base_url}/api/tags", timeout=5)
        else:
            resp = httpx.get(f"{base_url}/api/tags", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        pulled = [m["name"] for m in data.get("models", [])]
        # Match by prefix (e.g. "gemma:2b" matches "gemma:2b" or "gemma:2b-instruct")
        matched = [p for p in pulled if p.startswith(model.split(":")[0])]
        if matched:
            return VerifyResult(
                "ollama",
                ok=True,
                detail=f"Ollama running; {model} available as {matched[0]}",
            )
        return VerifyResult(
            "ollama",
            ok=False,
            detail=f"Ollama running but {model} not found. Pulled: {pulled or 'none'}",
        )
    except Exception as exc:
        return VerifyResult(
            "ollama",
            ok=False,
            detail=f"Ollama not reachable at {base_url}: {exc}",
        )


# ---------------------------------------------------------------------------
# Full stack verify
# ---------------------------------------------------------------------------


def verify_stack(
    acme_url: str = "http://localhost:8000",
    ollama_url: str = "http://localhost:11434",
    ollama_model: str = "gemma:2b",
    *,
    http_client: httpx.Client | None = None,
    cli_runner=None,
) -> list[VerifyResult]:
    """
    Run all component checks. Returns results in dependency order:
    acme-parts-cloud → fde-data-forge → rag-eval-bench → ollama.
    """
    return [
        check_acme_api(acme_url, client=http_client),
        check_fde_cli(runner=cli_runner),
        check_rag_cli(runner=cli_runner),
        check_ollama(ollama_url, ollama_model, client=http_client),
    ]
