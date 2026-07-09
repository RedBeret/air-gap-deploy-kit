"""Tests for the deployment verifier using pytest-httpx."""

import httpx
from pytest_httpx import HTTPXMock

from kit.deploy.verifier import (
    check_acme_api,
    check_fde_cli,
    check_ollama,
    check_rag_cli,
    verify_stack,
)

# ---------------------------------------------------------------------------
# acme-parts-cloud health check
# ---------------------------------------------------------------------------


def test_check_acme_api_ok(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="http://localhost:8000/health", json={"status": "ok"})
    with httpx.Client() as client:
        result = check_acme_api("http://localhost:8000", client=client)
    assert result.ok is True
    assert "200" in result.detail or "ok" in result.detail.lower()


def test_check_acme_api_wrong_body(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="http://localhost:8000/health", json={"status": "degraded"})
    with httpx.Client() as client:
        result = check_acme_api("http://localhost:8000", client=client)
    assert result.ok is False
    assert "unexpected body" in result.detail.lower()


def test_check_acme_api_connection_error():
    # No mock → actual connection refused → httpx.ConnectError
    import httpx as _httpx

    class FailClient:
        def get(self, url, **kwargs):
            raise _httpx.ConnectError("refused")

    result = check_acme_api("http://localhost:8000", client=FailClient())
    assert result.ok is False
    assert "refused" in result.detail.lower()


# ---------------------------------------------------------------------------
# Ollama check
# ---------------------------------------------------------------------------


def test_check_ollama_model_found(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="http://localhost:11434/api/tags",
        json={"models": [{"name": "gemma:2b"}, {"name": "llama3:8b"}]},
    )
    with httpx.Client() as client:
        result = check_ollama("http://localhost:11434", "gemma:2b", client=client)
    assert result.ok is True
    assert "gemma" in result.detail.lower()


def test_check_ollama_model_missing(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="http://localhost:11434/api/tags",
        json={"models": [{"name": "llama3:8b"}]},
    )
    with httpx.Client() as client:
        result = check_ollama("http://localhost:11434", "gemma:2b", client=client)
    assert result.ok is False
    assert "not found" in result.detail.lower()


def test_check_ollama_not_running():
    import httpx as _httpx

    class FailClient:
        def get(self, url, **kwargs):
            raise _httpx.ConnectError("refused")

    result = check_ollama("http://localhost:11434", client=FailClient())
    assert result.ok is False
    assert "not reachable" in result.detail.lower()


# ---------------------------------------------------------------------------
# CLI checks (subprocess mocking)
# ---------------------------------------------------------------------------


def test_check_fde_cli_ok():
    def fake_runner(cmd):
        if cmd == ["fde", "--help"]:
            return "Usage: fde [OPTIONS] COMMAND..."
        raise RuntimeError(f"Unexpected: {cmd}")

    result = check_fde_cli(runner=fake_runner)
    assert result.ok is True


def test_check_rag_cli_ok():
    def fake_runner(cmd):
        if cmd == ["rag-eval", "--help"]:
            return "Usage: rag-eval [OPTIONS] COMMAND..."
        raise RuntimeError(f"Unexpected: {cmd}")

    result = check_rag_cli(runner=fake_runner)
    assert result.ok is True


def test_check_fde_cli_not_found():
    def fake_runner(cmd):
        raise FileNotFoundError("fde not found")

    result = check_fde_cli(runner=fake_runner)
    assert result.ok is False
    assert "not found" in result.detail.lower()


# ---------------------------------------------------------------------------
# Full stack verify
# ---------------------------------------------------------------------------


def test_verify_stack_all_pass(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="http://localhost:8000/health", json={"status": "ok"})
    httpx_mock.add_response(
        url="http://localhost:11434/api/tags",
        json={"models": [{"name": "gemma:2b"}]},
    )

    def fake_cli(cmd):
        return "Usage: ..."

    with httpx.Client() as client:
        results = verify_stack(
            acme_url="http://localhost:8000",
            ollama_url="http://localhost:11434",
            ollama_model="gemma:2b",
            http_client=client,
            cli_runner=fake_cli,
        )

    assert len(results) == 4
    assert all(r.ok for r in results)
