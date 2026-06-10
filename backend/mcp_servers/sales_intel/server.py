"""
MCP Sales Intel server — wraps Open Sales Stack tools for Concierge orchestrator.

Provides techstack detection and website data extraction for lead research.
"""
import ipaddress
import json
import logging
import os
import socket
import sys
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


def _ssrf_check(hostname: str) -> str | None:
    """Resolve hostname and reject private/loopback/link-local/reserved targets.

    Returns an error message, or None if the host is safe to fetch.
    LLM передає сюди довільні URL, тому без цієї перевірки інструмент може
    сканувати внутрішні сервіси (redis, БД, cloud metadata 169.254.169.254).
    """
    if not hostname:
        return "URL has no hostname"
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return f"Cannot resolve hostname: {hostname}"
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            return f"Refusing to fetch internal/private address: {hostname} -> {ip}"
    return None


def _validate_external_url(url: str) -> str | None:
    """Return an error message if URL is not a safe external http(s) URL."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return f"Only http/https URLs are allowed, got scheme: {parsed.scheme or '(none)'}"
    return _ssrf_check(parsed.hostname or "")

# Path to open-sales-stack packages (mounted or copied into container)
OSS_BASE = os.environ.get(
    "OPEN_SALES_STACK_PATH",
    "/app/open_sales_stack_packages",
)

# Ensure .env is loaded for LLM_API_KEY
from dotenv import load_dotenv
load_dotenv(os.path.join(OSS_BASE, ".env"))

mcp = FastMCP("mcp-sales-intel")


@mcp.tool()
async def detect_techstack(
    client_id: int,
    session_id: str = "",
    domain: str = "",
) -> str:
    """Detect technology stack of a company website.
    Returns CRM, analytics, frameworks, hosting, email providers, etc.
    Use when researching a company or qualifying a lead."""

    if not domain:
        return json.dumps({"error": "domain is required, e.g. 'stripe.com'"})

    ssrf_error = _ssrf_check(domain.split("/")[0].split(":")[0])
    if ssrf_error:
        return json.dumps({"error": ssrf_error})

    pkg_dir = os.path.join(OSS_BASE, "techstack-intel")
    if pkg_dir not in sys.path:
        sys.path.insert(0, pkg_dir)
    old_cwd = os.getcwd()
    os.chdir(pkg_dir)

    try:
        from tools.detect_techstack import detect_techstack as _detect
        result = await _detect(domain)
        return result
    except Exception as e:
        logger.exception("techstack detection failed for %s", domain)
        return json.dumps({"error": str(e)})
    finally:
        os.chdir(old_cwd)


@mcp.tool()
async def website_extract(
    client_id: int,
    session_id: str = "",
    url: str = "",
    schema: dict = None,
    prompt: str = "",
    mode: str = "scrape",
    limit: int = 5,
) -> str:
    """Scrape a webpage and extract structured data using LLM.
    Provide a URL, a JSON schema for the output shape, and a prompt
    describing what to extract. Use for company research, pricing pages,
    team pages, product info.

    Example schema: {"type": "object", "properties": {"company_name": {"type": "string"}, "pricing_plans": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "price": {"type": "string"}}}}}}
    Example prompt: "Extract company name and all pricing plans with names and prices"
    """

    if not url:
        return json.dumps({"error": "url is required"})
    if not schema:
        return json.dumps({"error": "schema is required (JSON Schema object)"})
    if not prompt:
        return json.dumps({"error": "prompt is required (what to extract)"})

    ssrf_error = _validate_external_url(url)
    if ssrf_error:
        return json.dumps({"error": ssrf_error})

    pkg_dir = os.path.join(OSS_BASE, "website-intel")
    if pkg_dir not in sys.path:
        sys.path.insert(0, pkg_dir)
    old_cwd = os.getcwd()
    os.chdir(pkg_dir)

    try:
        from tools.extract import website_intel_extract as _extract
        result = await _extract(url, schema, prompt, mode, min(max(limit, 1), 10))
        return result
    except Exception as e:
        logger.exception("website extraction failed for %s", url)
        return json.dumps({"error": str(e)})
    finally:
        os.chdir(old_cwd)


if __name__ == "__main__":
    mcp.run(transport="stdio")
