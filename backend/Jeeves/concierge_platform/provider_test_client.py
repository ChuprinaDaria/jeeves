"""Stateless client for 'Test connection' actions on AI providers.

Every public function returns a TestResult. Functions never raise —
any exception is caught and mapped to network_error. These are called
from DRF action views but must never mutate DB state.
"""
from dataclasses import dataclass, field
from typing import Literal, Optional

import requests

Outcome = Literal["success", "invalid_key", "network_error"]

_TIMEOUT = 10


@dataclass
class TestResult:
    outcome: Outcome
    message: str = ""
    metadata: dict = field(default_factory=dict)


def _auth_error(resp: requests.Response) -> bool:
    return resp.status_code in (401, 403)


def _network_error(msg: str) -> TestResult:
    return TestResult(outcome="network_error", message=msg)


def _count_models_or_one(payload: dict) -> int:
    for key in ("data", "models"):
        value = payload.get(key)
        if isinstance(value, list):
            return len(value)
    return 1


def test_llm_provider(
    provider_type: str,
    api_key: str,
    api_endpoint: Optional[str] = None,
    model_name: Optional[str] = None,
) -> TestResult:
    """Dispatch to provider-specific test call. Never raises."""
    try:
        if provider_type == "openai":
            return _get_with_bearer("https://api.openai.com/v1/models", api_key)
        if provider_type == "anthropic":
            return _get_with_header(
                "https://api.anthropic.com/v1/models",
                {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            )
        if provider_type == "cohere":
            return _get_with_bearer("https://api.cohere.ai/v1/models", api_key)
        if provider_type == "kimi":
            return _get_with_bearer("https://api.moonshot.cn/v1/models", api_key)
        if provider_type in ("ollama_main", "ollama_light", "custom"):
            if not api_endpoint:
                return _network_error("api_endpoint is required for Ollama/custom")
            url = api_endpoint.rstrip("/") + "/api/tags"
            return _plain_get(url)
        return _network_error("Unsupported provider for test")
    except requests.Timeout as exc:
        return _network_error(f"Timeout: {exc}")
    except requests.ConnectionError as exc:
        return _network_error(f"Connection error: {exc}")
    except Exception as exc:  # noqa: BLE001
        return _network_error(f"Unexpected error: {exc}")


def _get_with_bearer(url: str, api_key: str) -> TestResult:
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=_TIMEOUT,
    )
    return _interpret_list_response(resp)


def _get_with_header(url: str, headers: dict) -> TestResult:
    resp = requests.get(url, headers=headers, timeout=_TIMEOUT)
    return _interpret_list_response(resp)


def _plain_get(url: str) -> TestResult:
    resp = requests.get(url, timeout=_TIMEOUT)
    return _interpret_list_response(resp)


def _interpret_list_response(resp: requests.Response) -> TestResult:
    if _auth_error(resp):
        return TestResult(
            outcome="invalid_key",
            message=f"Invalid API key (HTTP {resp.status_code})",
        )
    if resp.status_code >= 500:
        return _network_error(f"Upstream server error (HTTP {resp.status_code})")
    if resp.status_code >= 400:
        return _network_error(f"HTTP {resp.status_code}")
    try:
        payload = resp.json() or {}
    except ValueError:
        payload = {}
    count = _count_models_or_one(payload)
    return TestResult(
        outcome="success",
        message=f"Connected. {count} models available",
        metadata={"models_count": count},
    )


def test_embedding_model(
    provider: str,
    api_key: str,
    model_name: str,
    dimensions: int,
    api_endpoint: Optional[str] = None,
) -> TestResult:
    try:
        if provider == "openai":
            return _openai_embedding(api_key, model_name, dimensions)
        if provider == "cohere":
            return _cohere_embedding(api_key, model_name, dimensions)
        if provider == "anthropic":
            return _network_error(
                "Anthropic does not expose an embedding API test endpoint yet",
            )
        if provider == "huggingface":
            return _huggingface_embedding(
                api_key, model_name, dimensions, api_endpoint,
            )
        return _network_error("Unsupported provider for test")
    except requests.Timeout as exc:
        return _network_error(f"Timeout: {exc}")
    except requests.ConnectionError as exc:
        return _network_error(f"Connection error: {exc}")
    except Exception as exc:  # noqa: BLE001
        return _network_error(f"Unexpected error: {exc}")


def _openai_embedding(api_key: str, model_name: str, dimensions: int) -> TestResult:
    resp = requests.post(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"input": "hello", "model": model_name},
        timeout=_TIMEOUT,
    )
    return _interpret_embedding_response(resp, dimensions)


def _cohere_embedding(api_key: str, model_name: str, dimensions: int) -> TestResult:
    resp = requests.post(
        "https://api.cohere.ai/v1/embed",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"texts": ["hello"], "model": model_name},
        timeout=_TIMEOUT,
    )
    if _auth_error(resp):
        return TestResult(outcome="invalid_key", message="Invalid API key")
    if resp.status_code >= 400:
        return _network_error(f"HTTP {resp.status_code}")
    try:
        payload = resp.json() or {}
    except ValueError:
        payload = {}
    vecs = payload.get("embeddings") or []
    actual = len(vecs[0]) if vecs and isinstance(vecs[0], list) else 0
    if actual != dimensions:
        return TestResult(
            outcome="success",
            message=(
                f"Connected but dimension mismatch: model returned {actual}, "
                f"config says {dimensions}"
            ),
            metadata={"actual_dimensions": actual},
        )
    return TestResult(
        outcome="success",
        message=f"Connected. {actual}-dim vector",
        metadata={"actual_dimensions": actual},
    )


def _huggingface_embedding(
    api_key: str, model_name: str, dimensions: int, api_endpoint: Optional[str],
) -> TestResult:
    url = api_endpoint or (
        f"https://api-inference.huggingface.co/pipeline/feature-extraction/{model_name}"
    )
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    resp = requests.post(
        url, headers=headers, json={"inputs": "hello"}, timeout=_TIMEOUT,
    )
    return _interpret_embedding_response(resp, dimensions)


def _interpret_embedding_response(
    resp: requests.Response, expected_dimensions: int,
) -> TestResult:
    if _auth_error(resp):
        return TestResult(outcome="invalid_key", message="Invalid API key")
    if resp.status_code >= 400:
        return _network_error(f"HTTP {resp.status_code}")
    try:
        payload = resp.json() or {}
    except ValueError:
        payload = {}
    data = payload.get("data") or []
    if data and isinstance(data, list):
        vec = data[0].get("embedding") if isinstance(data[0], dict) else None
    else:
        vec = payload if isinstance(payload, list) else None
    actual = len(vec) if isinstance(vec, list) else 0
    if actual and actual != expected_dimensions:
        return TestResult(
            outcome="success",
            message=(
                f"Connected but dimension mismatch: provider returned {actual}, "
                f"config says {expected_dimensions}"
            ),
            metadata={"actual_dimensions": actual},
        )
    return TestResult(
        outcome="success",
        message=f"Connected. {actual}-dim vector",
        metadata={"actual_dimensions": actual},
    )
