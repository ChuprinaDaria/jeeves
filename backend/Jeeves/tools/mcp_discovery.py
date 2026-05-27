# backend/Jeeves/tools/mcp_discovery.py
import asyncio
import json
import logging
import re
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

DISCOVERY_TIMEOUT = 10  # seconds


@dataclass
class DiscoveryResult:
    server_name: str
    tools: list  # [{"name": ..., "description": ..., "inputSchema": ...}]
    transport: str = ""  # "sse" | "streamable_http"


@dataclass
class PageParseResult:
    """Info extracted from a catalog page about an MCP server."""
    server_name: str = ""
    github_url: str = ""
    npm_package: str = ""
    pip_package: str = ""
    sse_endpoint: str = ""
    install_command: str = ""
    mcp_config: dict = field(default_factory=dict)
    description: str = ""
    transport_type: str = ""  # "stdio" | "sse" | "streamable_http"


class DiscoveryError(Exception):
    pass


def _fetch_page(url: str) -> str:
    """Fetch page content as text."""
    with httpx.Client(timeout=10, follow_redirects=True) as client:
        resp = client.get(url, headers={"User-Agent": "Jeeves-MCP-Discovery/1.0"})
        resp.raise_for_status()
        return resp.text


def _is_html(url: str) -> bool:
    """Quick HEAD check to see if URL serves HTML."""
    try:
        with httpx.Client(timeout=5, follow_redirects=True) as client:
            resp = client.head(url)
            return "text/html" in resp.headers.get("content-type", "")
    except Exception:
        return False


def _parse_catalog_page(html: str, source_url: str) -> PageParseResult:
    """Extract MCP server info from a catalog page HTML."""
    result = PageParseResult()

    # Server name — look for <h1> or <title>
    h1 = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
    if h1:
        name = h1.group(1).strip()
        # Clean up common suffixes
        for suffix in [" MCP Server", " - MCP", " MCP"]:
            if name.endswith(suffix):
                name = name[:-len(suffix)].strip()
        result.server_name = name

    # GitHub URL
    gh = re.search(r'https://github\.com/[\w.-]+/[\w.-]+', html)
    if gh:
        result.github_url = gh.group(0).rstrip('/')

    # npm package — npx or npm install (package must start with letter or @)
    npm = re.search(r'npx\s+(?:-y\s+)?(@[\w./-]+|[a-zA-Z][\w./-]*)', html)
    if npm:
        result.npm_package = npm.group(1)
    else:
        npm_install = re.search(r'npm\s+install\s+(?:-g\s+)?(@[\w./-]+|[a-zA-Z][\w./-]*)', html)
        if npm_install:
            result.npm_package = npm_install.group(1)

    # pip package — must start with letter
    pip = re.search(r'(?:pip|pip3|uv pip)\s+install\s+([a-zA-Z][\w.-]*)', html)
    if pip:
        result.pip_package = pip.group(1)
    else:
        uvx = re.search(r'uvx\s+([a-zA-Z][\w.-]*)', html)
        if uvx:
            result.pip_package = uvx.group(1)

    # SSE/HTTP endpoint URLs — must end with /sse, exclude known false positives
    sse = re.search(r'(https?://[^\s"\'<>]+/sse)\b', html)
    if sse:
        ep = sse.group(1)
        # Reject known false positives (GitHub, Google, etc.)
        if not any(host in ep for host in ['github.com', 'google.com', 'stackoverflow.com']):
            result.sse_endpoint = ep

    # MCP JSON config blocks — look for {"command": ..., "args": [...]}
    json_blocks = re.findall(r'\{[^{}]*"command"\s*:\s*"[^"]+?"[^{}]*\}', html)
    for block in json_blocks:
        try:
            # Unescape HTML entities
            clean = block.replace('&quot;', '"').replace('&#39;', "'").replace('&amp;', '&')
            parsed = json.loads(clean)
            if "command" in parsed:
                result.mcp_config = parsed
                break
        except (json.JSONDecodeError, ValueError):
            continue

    # Also try larger JSON blocks with "mcpServers" key
    if not result.mcp_config:
        mcp_servers_blocks = re.findall(r'\{[^{}]*"mcpServers"[^}]*\{[^}]+\}[^}]*\}', html)
        for block in mcp_servers_blocks:
            try:
                clean = block.replace('&quot;', '"').replace('&#39;', "'").replace('&amp;', '&')
                parsed = json.loads(clean)
                servers = parsed.get("mcpServers", {})
                if servers:
                    # Take first server config
                    first_config = next(iter(servers.values()))
                    if "command" in first_config:
                        result.mcp_config = first_config
                        result.server_name = result.server_name or next(iter(servers.keys()))
                        break
            except (json.JSONDecodeError, ValueError, StopIteration):
                continue

    # Install command — curl | sh or brew install
    install = re.search(r'(curl\s+[^\n]+install[^\n]+)', html)
    if install:
        result.install_command = install.group(1).strip()

    # Determine transport type
    if result.sse_endpoint:
        result.transport_type = "sse"
    elif result.mcp_config.get("command") or result.npm_package or result.pip_package:
        result.transport_type = "stdio"
    else:
        result.transport_type = ""

    # Description — meta description
    meta_desc = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
    if meta_desc:
        result.description = meta_desc.group(1).strip()

    return result


async def _discover_sse(url: str) -> DiscoveryResult:
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    async with sse_client(url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            tools = [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "inputSchema": t.inputSchema if hasattr(t, "inputSchema") else {},
                }
                for t in result.tools
            ]
            server_name = getattr(session, "server_name", "") or ""
            return DiscoveryResult(server_name=server_name, tools=tools, transport="sse")


async def _discover_streamable_http(url: str) -> DiscoveryResult:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            tools = [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "inputSchema": t.inputSchema if hasattr(t, "inputSchema") else {},
                }
                for t in result.tools
            ]
            server_name = getattr(session, "server_name", "") or ""
            return DiscoveryResult(server_name=server_name, tools=tools, transport="streamable_http")


def _discover_live(url: str) -> DiscoveryResult:
    """Try to connect to a live MCP endpoint via Streamable HTTP, then SSE."""
    errors = []
    for transport_name, coro_fn in [
        ("Streamable HTTP", _discover_streamable_http),
        ("SSE", _discover_sse),
    ]:
        try:
            result = asyncio.run(
                asyncio.wait_for(coro_fn(url), timeout=DISCOVERY_TIMEOUT)
            )
            if not result.tools:
                raise DiscoveryError("Server returned zero tools.")
            return result
        except DiscoveryError:
            raise
        except asyncio.TimeoutError:
            errors.append(f"{transport_name}: timed out after {DISCOVERY_TIMEOUT}s")
        except Exception as e:
            errors.append(f"{transport_name}: {e}")

    raise DiscoveryError(
        "Could not connect via any transport. " + "; ".join(errors)
    )


async def _discover_stdio(command: str, args: list, env: dict = None) -> DiscoveryResult:
    """Connect to a local MCP server via stdio and list tools."""
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters

    server_params = StdioServerParameters(
        command=command,
        args=args,
        env=env,
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            tools = [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "inputSchema": t.inputSchema if hasattr(t, "inputSchema") else {},
                }
                for t in result.tools
            ]
            server_name = getattr(session, "server_name", "") or ""
            return DiscoveryResult(server_name=server_name, tools=tools, transport="stdio")


def _preflight_stdio(command: str, args: list, env: dict = None) -> None:
    """Quick check: run the server and see if it crashes immediately with an error message.

    If it exits with non-zero within 3s, capture stderr and raise DiscoveryError.
    If it stays running or exits cleanly, do nothing — let the real discovery handle it.
    """
    import subprocess
    try:
        proc = subprocess.run(
            [command] + args,
            capture_output=True, text=True, timeout=3,
            env=env,
        )
        if proc.returncode != 0 and proc.stderr.strip():
            raise DiscoveryError(proc.stderr.strip())
        if proc.returncode != 0 and proc.stdout.strip():
            raise DiscoveryError(proc.stdout.strip())
    except subprocess.TimeoutExpired:
        pass  # server stayed alive — good, let stdio discovery handle it
    except DiscoveryError:
        raise
    except FileNotFoundError:
        raise DiscoveryError(f"Command not found: {command}")
    except Exception:
        pass


def discover_stdio(command: str, args: list = None, env: dict = None) -> DiscoveryResult:
    """Discover tools from a local stdio MCP server."""
    # Quick preflight — catch fast crashes with useful error messages
    _preflight_stdio(command, args or [], env)

    try:
        result = asyncio.run(
            asyncio.wait_for(
                _discover_stdio(command, args or [], env),
                timeout=DISCOVERY_TIMEOUT,
            )
        )
        if not result.tools:
            raise DiscoveryError("Server returned zero tools.")
        return result
    except DiscoveryError:
        raise
    except asyncio.TimeoutError:
        raise DiscoveryError(f"Stdio server timed out after {DISCOVERY_TIMEOUT}s.")
    except FileNotFoundError:
        raise DiscoveryError(f"Command not found: {command}")
    except Exception as e:
        raise DiscoveryError(f"Stdio connection failed: {e}")


def install_npm_package(package_name: str) -> str:
    """Install an npm package globally. Returns installed version.

    Raises DiscoveryError if install fails or package has no bin entry.
    """
    import subprocess
    try:
        result = subprocess.run(
            ["npm", "install", "-g", package_name],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            raise DiscoveryError(f"npm install failed: {result.stderr.strip()}")

        # Check if package has a bin entry (required for npx to work)
        root_result = subprocess.run(
            ["npm", "root", "-g"], capture_output=True, text=True, timeout=10,
        )
        if root_result.returncode == 0:
            import os
            pkg_json_path = os.path.join(root_result.stdout.strip(), package_name, "package.json")
            try:
                with open(pkg_json_path) as f:
                    pkg_data = json.load(f)
                if not pkg_data.get("bin"):
                    raise DiscoveryError(
                        f"Package {package_name} installed but has no executable (no 'bin' in package.json). "
                        f"This is likely a client SDK, not an MCP server."
                    )
            except FileNotFoundError:
                pass
            except DiscoveryError:
                raise

        # Get version
        ver = subprocess.run(
            ["npm", "list", "-g", package_name, "--depth=0", "--json"],
            capture_output=True, text=True, timeout=10,
        )
        version = ""
        if ver.returncode == 0:
            try:
                data = json.loads(ver.stdout)
                deps = data.get("dependencies", {})
                pkg = package_name.split("/")[-1]
                version = deps.get(package_name, deps.get(pkg, {})).get("version", "")
            except (json.JSONDecodeError, KeyError):
                pass
        return version
    except DiscoveryError:
        raise
    except subprocess.TimeoutExpired:
        raise DiscoveryError("npm install timed out (120s).")


def install_pip_package(package_name: str) -> str:
    """Install a pip package. Returns installed version."""
    import subprocess
    try:
        result = subprocess.run(
            ["pip", "install", package_name],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            raise DiscoveryError(f"pip install failed: {result.stderr.strip()}")
        ver = subprocess.run(
            ["pip", "show", package_name],
            capture_output=True, text=True, timeout=10,
        )
        version = ""
        if ver.returncode == 0:
            for line in ver.stdout.splitlines():
                if line.startswith("Version:"):
                    version = line.split(":", 1)[1].strip()
                    break
        return version
    except subprocess.TimeoutExpired:
        raise DiscoveryError("pip install timed out (120s).")


def discover_or_parse(url: str):
    """Smart discovery: if URL is a live MCP endpoint, discover tools.
    If it's an HTML page, parse it for server info.

    Returns either DiscoveryResult or PageParseResult.
    """
    if not _is_html(url):
        return _discover_live(url)

    # It's a catalog page — parse for install info
    try:
        html = _fetch_page(url)
    except Exception as e:
        raise DiscoveryError(f"Failed to fetch page: {e}")

    parsed = _parse_catalog_page(html, url)

    # If page has a remote endpoint, try to connect to it
    if parsed.sse_endpoint:
        try:
            result = _discover_live(parsed.sse_endpoint)
            result.server_name = result.server_name or parsed.server_name
            return result
        except DiscoveryError:
            pass  # fall through to return parsed page info

    if not parsed.server_name and not parsed.mcp_config and not parsed.npm_package:
        raise DiscoveryError(
            "Could not find MCP server information on this page. "
            "Try pasting the direct MCP endpoint URL or the GitHub repository URL."
        )

    return parsed
