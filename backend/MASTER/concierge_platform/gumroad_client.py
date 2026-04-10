"""Isolated HTTP client for the Gumroad license verify API.

All HTTP access to Gumroad happens here so tests can mock a single
integration point. `verify_license()` never raises — it always returns
a `GumroadResult`.
"""
from dataclasses import dataclass, field
from typing import Literal

import requests
from django.conf import settings

GUMROAD_VERIFY_URL = "https://api.gumroad.com/v2/licenses/verify"
GUMROAD_TIMEOUT_SECONDS = 10


Outcome = Literal["valid", "invalid", "network_error"]


@dataclass
class GumroadResult:
    outcome: Outcome
    data: dict = field(default_factory=dict)
    error: str = ""


def verify_license(license_key: str) -> GumroadResult:
    """Call Gumroad verify API, never raises.

    Reads GUMROAD_PRODUCT_ID from Django settings. Returns a GumroadResult
    describing one of three outcomes:

    - valid:         Gumroad returned success=True. `data` contains uses + purchase.
    - invalid:       Gumroad returned success=False. `error` contains the message.
    - network_error: Any transport-level problem (timeout, DNS, 5xx, non-JSON).
    """
    product_id = settings.GUMROAD_PRODUCT_ID
    payload = {
        "product_id": product_id,
        "license_key": license_key,
    }
    try:
        response = requests.post(
            GUMROAD_VERIFY_URL,
            data=payload,
            timeout=GUMROAD_TIMEOUT_SECONDS,
        )
    except requests.Timeout:
        return GumroadResult(outcome="network_error", error="timeout")
    except requests.ConnectionError as exc:
        return GumroadResult(outcome="network_error", error=f"connection_error: {exc}")
    except requests.RequestException as exc:
        return GumroadResult(outcome="network_error", error=f"request_error: {exc}")

    if response.status_code != 200:
        return GumroadResult(
            outcome="network_error",
            error=f"HTTP {response.status_code}: {response.text[:200]}",
        )

    try:
        body = response.json()
    except ValueError:
        return GumroadResult(outcome="network_error", error="malformed_json")

    if body.get("success") is True:
        return GumroadResult(outcome="valid", data=body)

    message = body.get("message") or "Gumroad rejected the license key"
    return GumroadResult(outcome="invalid", error=message, data=body)
