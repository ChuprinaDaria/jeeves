# MCP Auto-Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow owner to paste a URL (mcpservers.org, npm, pypi, GitHub, or package name) and have the system automatically resolve, install, and register the MCP server for assignment to specific clients.

**Architecture:** Extend existing `mcp_discovery.py` with a resolver chain that converts URLs to package info, then install via subprocess and discover tools via stdio. New `InstalledMCPServer` model links `ToolCard` to package metadata. Orchestrator reads both `settings.MCP_SERVERS` and `InstalledMCPServer` records on connect.

**Tech Stack:** Django 5.x, DRF, MCP Python SDK (stdio_client), npm/pip CLI, React 18

---

## File Structure

### Backend — new files
- `backend/Jeeves/tools/resolvers.py` — URL resolution chain (McpServersOrg, Npm, Pypi, GitHub, DirectName)
- `backend/Jeeves/tools/installer.py` — package install + stdio discovery logic
- `backend/Jeeves/tools/migrations/XXXX_add_installed_mcp_server.py` — auto-generated migration
- `backend/Jeeves/tools/tests/test_resolvers.py` — resolver unit tests
- `backend/Jeeves/tools/tests/__init__.py` — package init
- `backend/Jeeves/tools/tests/test_installer.py` — installer tests

### Backend — modified files
- `backend/Jeeves/tools/models.py` — add `InstalledMCPServer` model, add `'stdio'` to `TRANSPORT_CHOICES`
- `backend/Jeeves/tools/mcp_discovery.py` — extend to support stdio discovery + URL resolution
- `backend/Jeeves/tools/views_owner.py` — update discover/from_url actions for new flow
- `backend/Jeeves/tools/serializers_owner.py` — add client selection, credentials fields
- `backend/Jeeves/agents/orchestrator.py` — read `InstalledMCPServer` in `connect()`

### Frontend — modified files
- `frontend/src/pages/owner/MCPServerEditPage.jsx` — add credentials form, client selection, install status
- `frontend/src/api/owner.js` — update `mcpServersAPI` if needed

---

### Task 1: Add InstalledMCPServer model

**Files:**
- Modify: `backend/Jeeves/tools/models.py`
- Create: `backend/Jeeves/tools/tests/__init__.py`
- Create: `backend/Jeeves/tools/tests/test_resolvers.py` (placeholder for Task 3)

- [ ] **Step 1: Add stdio to TRANSPORT_CHOICES and create InstalledMCPServer model**

In `backend/Jeeves/tools/models.py`, add `'stdio'` to `TRANSPORT_CHOICES` on the `ToolCard` model:

```python
TRANSPORT_CHOICES = [
    ('builtin', 'Built-in Django handler'),
    ('sse', 'SSE (Server-Sent Events)'),
    ('streamable_http', 'Streamable HTTP'),
    ('stdio', 'Stdio (local subprocess)'),
]
```

Then add the new model at the bottom of the file:

```python
class InstalledMCPServer(models.Model):
    """Tracks an npm/pypi MCP server package installed by the owner."""

    PACKAGE_TYPE_CHOICES = [
        ('npm', 'npm'),
        ('pypi', 'PyPI'),
    ]

    STATUS_CHOICES = [
        ('installed', 'Installed'),
        ('failed', 'Failed'),
        ('removed', 'Removed'),
    ]

    tool_card = models.OneToOneField(
        ToolCard, on_delete=models.CASCADE, related_name='installed_server',
    )
    package_name = models.CharField(max_length=255, unique=True)
    package_type = models.CharField(max_length=10, choices=PACKAGE_TYPE_CHOICES)
    version = models.CharField(max_length=50, blank=True)
    run_command = models.CharField(max_length=500)
    run_args = models.JSONField(default=list, blank=True)
    env_config = models.JSONField(default=dict, blank=True)
    source_url = models.URLField(blank=True)
    installed_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='installed',
    )
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-installed_at']

    def __str__(self):
        return f"{self.package_name} ({self.package_type})"
```

- [ ] **Step 2: Create and run migration**

```bash
cd /home/dchuprina/jeevs/backend
docker compose exec web python manage.py makemigrations tools --name add_installed_mcp_server
docker compose exec web python manage.py migrate
```

Expected: migration created and applied successfully.

- [ ] **Step 3: Commit**

```bash
git add backend/Jeeves/tools/models.py backend/Jeeves/tools/migrations/
git commit -m "feat(tools): add InstalledMCPServer model and stdio transport type"
```

---

### Task 2: URL Resolver Chain

**Files:**
- Create: `backend/Jeeves/tools/resolvers.py`
- Create: `backend/Jeeves/tools/tests/test_resolvers.py`

- [ ] **Step 1: Write tests for resolvers**

Create `backend/Jeeves/tools/tests/__init__.py` (empty file).

Create `backend/Jeeves/tools/tests/test_resolvers.py`:

```python
from unittest.mock import patch, MagicMock
import pytest

from Jeeves.tools.resolvers import resolve_url, ResolvedPackage, ResolutionError


class TestNpmResolver:
    @patch('Jeeves.tools.resolvers.httpx')
    def test_npm_url(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'name': 'mcp-ukrainian-calendar',
            'version': '1.0.5',
            'description': 'Ukrainian calendar MCP server',
            'homepage': 'https://github.com/ChuprinaDaria/mcp-ukrainian-calendar',
            'readme': 'Set API_KEY env var to configure',
        }
        mock_httpx.get.return_value = mock_resp

        result = resolve_url('https://www.npmjs.com/package/mcp-ukrainian-calendar')

        assert isinstance(result, ResolvedPackage)
        assert result.package_name == 'mcp-ukrainian-calendar'
        assert result.package_type == 'npm'
        assert result.version == '1.0.5'
        assert result.run_command == 'npx'
        assert result.run_args == ['-y', 'mcp-ukrainian-calendar']

    @patch('Jeeves.tools.resolvers.httpx')
    def test_npm_scoped_package(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'name': '@anthropic/mcp-server',
            'version': '2.0.0',
            'description': 'Anthropic MCP server',
            'homepage': '',
            'readme': '',
        }
        mock_httpx.get.return_value = mock_resp

        result = resolve_url('https://www.npmjs.com/package/@anthropic/mcp-server')

        assert result.package_name == '@anthropic/mcp-server'
        assert result.run_args == ['-y', '@anthropic/mcp-server']


class TestPypiResolver:
    @patch('Jeeves.tools.resolvers.httpx')
    def test_pypi_url(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'info': {
                'name': 'mcp-server-fetch',
                'version': '0.6.2',
                'summary': 'MCP server for web fetching',
                'home_page': '',
                'description': '',
            },
        }
        mock_httpx.get.return_value = mock_resp

        result = resolve_url('https://pypi.org/project/mcp-server-fetch/')

        assert result.package_name == 'mcp-server-fetch'
        assert result.package_type == 'pypi'
        assert result.run_command == 'python'
        assert result.run_args == ['-m', 'mcp_server_fetch']


class TestMcpServersOrgResolver:
    @patch('Jeeves.tools.resolvers.httpx')
    def test_mcpservers_org_with_npm_link(self, mock_httpx):
        html_resp = MagicMock()
        html_resp.status_code = 200
        html_resp.text = '''
        <html>
        <a href="https://www.npmjs.com/package/mcp-ukrainian-calendar">npm</a>
        </html>
        '''

        npm_resp = MagicMock()
        npm_resp.status_code = 200
        npm_resp.json.return_value = {
            'name': 'mcp-ukrainian-calendar',
            'version': '1.0.5',
            'description': 'Ukrainian calendar',
            'homepage': '',
            'readme': '',
        }

        mock_httpx.get.side_effect = [html_resp, npm_resp]

        result = resolve_url(
            'https://mcpservers.org/servers/chuprinadaria/mcp-ukrainian-calendar'
        )
        assert result.package_name == 'mcp-ukrainian-calendar'
        assert result.package_type == 'npm'


class TestDirectNameResolver:
    @patch('Jeeves.tools.resolvers.httpx')
    def test_plain_package_name_npm(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'name': 'mcp-ukrainian-calendar',
            'version': '1.0.5',
            'description': 'Ukrainian calendar',
            'homepage': '',
            'readme': '',
        }
        mock_httpx.get.return_value = mock_resp

        result = resolve_url('mcp-ukrainian-calendar')
        assert result.package_type == 'npm'

    @patch('Jeeves.tools.resolvers.httpx')
    def test_plain_package_name_pypi_fallback(self, mock_httpx):
        npm_resp = MagicMock()
        npm_resp.status_code = 404

        pypi_resp = MagicMock()
        pypi_resp.status_code = 200
        pypi_resp.json.return_value = {
            'info': {
                'name': 'some-mcp-server',
                'version': '0.1.0',
                'summary': 'A server',
                'home_page': '',
                'description': '',
            },
        }

        mock_httpx.get.side_effect = [npm_resp, pypi_resp]

        result = resolve_url('some-mcp-server')
        assert result.package_type == 'pypi'


class TestGitHubResolver:
    @patch('Jeeves.tools.resolvers.httpx')
    def test_github_url_with_package_json(self, mock_httpx):
        pkg_resp = MagicMock()
        pkg_resp.status_code = 200
        pkg_resp.json.return_value = {
            'name': 'mcp-calendar',
            'version': '1.0.0',
            'description': 'Calendar MCP',
        }

        npm_resp = MagicMock()
        npm_resp.status_code = 200
        npm_resp.json.return_value = {
            'name': 'mcp-calendar',
            'version': '1.0.0',
            'description': 'Calendar MCP',
            'homepage': '',
            'readme': '',
        }

        mock_httpx.get.side_effect = [pkg_resp, npm_resp]

        result = resolve_url('https://github.com/user/mcp-calendar')
        assert result.package_type == 'npm'
        assert result.package_name == 'mcp-calendar'


class TestResolutionError:
    def test_invalid_url_raises(self):
        with pytest.raises(ResolutionError):
            resolve_url('')

    @patch('Jeeves.tools.resolvers.httpx')
    def test_unknown_url_raises(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_httpx.get.return_value = mock_resp

        with pytest.raises(ResolutionError):
            resolve_url('https://random-site.com/something')


class TestCredentialDetection:
    @patch('Jeeves.tools.resolvers.httpx')
    def test_detects_env_vars_in_readme(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'name': 'mcp-firecrawl',
            'version': '1.0.0',
            'description': 'Firecrawl MCP',
            'homepage': '',
            'readme': '''
# Setup
Set the following environment variables:
- `FIRECRAWL_API_KEY` - your API key
- `FIRECRAWL_SECRET` - your secret
            ''',
        }
        mock_httpx.get.return_value = mock_resp

        result = resolve_url('https://www.npmjs.com/package/mcp-firecrawl')
        assert result.requires_credentials is True
        assert 'FIRECRAWL_API_KEY' in result.env_vars
        assert 'FIRECRAWL_SECRET' in result.env_vars
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/dchuprina/jeevs/backend
docker compose exec web python -m pytest Jeeves/tools/tests/test_resolvers.py -v 2>&1 | head -40
```

Expected: ImportError — `Jeeves.tools.resolvers` does not exist yet.

- [ ] **Step 3: Implement resolvers**

Create `backend/Jeeves/tools/resolvers.py`:

```python
import re
import logging
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# Patterns that indicate required credentials in README text
_CREDENTIAL_PATTERNS = re.compile(
    r'[A-Z][A-Z0-9_]*(?:_API_KEY|_SECRET|_TOKEN|_PASSWORD|_CREDENTIALS)',
)


@dataclass
class ResolvedPackage:
    package_name: str
    package_type: str          # "npm" | "pypi"
    version: str = ''
    description: str = ''
    homepage: str = ''
    run_command: str = ''
    run_args: list = field(default_factory=list)
    env_vars: list = field(default_factory=list)
    requires_credentials: bool = False


class ResolutionError(Exception):
    pass


def resolve_url(url_or_name: str) -> ResolvedPackage:
    """Resolve a URL or package name to a ResolvedPackage.

    Tries resolvers in order:
    1. mcpservers.org catalog page
    2. npmjs.com package URL
    3. pypi.org project URL
    4. github.com repository
    5. Plain package name (npm first, then pypi)
    """
    text = url_or_name.strip()
    if not text:
        raise ResolutionError('URL or package name is required.')

    # Not a URL — try direct name resolution
    if not text.startswith('http://') and not text.startswith('https://'):
        return _resolve_direct_name(text)

    parsed = urlparse(text)
    host = parsed.hostname or ''

    if 'mcpservers.org' in host:
        return _resolve_mcpservers_org(text)
    if 'npmjs.com' in host:
        return _resolve_npm_url(text)
    if 'pypi.org' in host:
        return _resolve_pypi_url(text)
    if 'github.com' in host:
        return _resolve_github(text)

    raise ResolutionError(
        f'Unsupported URL: {text}. '
        'Supported: mcpservers.org, npmjs.com, pypi.org, github.com, '
        'or a plain package name.'
    )


def _detect_credentials(readme: str) -> tuple[bool, list[str]]:
    """Scan README text for env var patterns that look like credentials."""
    if not readme:
        return False, []
    found = list(set(_CREDENTIAL_PATTERNS.findall(readme)))
    return bool(found), sorted(found)


# ── npm ──────────────────────────────────────────────────────────────

def _extract_npm_package_name(url: str) -> str:
    """Extract package name from npmjs.com URL."""
    # https://www.npmjs.com/package/mcp-ukrainian-calendar
    # https://www.npmjs.com/package/@scope/name
    path = urlparse(url).path  # /package/mcp-ukrainian-calendar
    match = re.match(r'^/package/(.+?)/?$', path)
    if not match:
        raise ResolutionError(f'Cannot parse npm package name from: {url}')
    return match.group(1)


def _fetch_npm_metadata(package_name: str) -> ResolvedPackage:
    """Fetch package metadata from npm registry."""
    registry_url = f'https://registry.npmjs.org/{package_name}/latest'
    resp = httpx.get(registry_url)
    if resp.status_code != 200:
        raise ResolutionError(f'npm package not found: {package_name}')

    data = resp.json()
    readme = data.get('readme', '')
    requires_creds, env_vars = _detect_credentials(readme)

    return ResolvedPackage(
        package_name=data.get('name', package_name),
        package_type='npm',
        version=data.get('version', ''),
        description=data.get('description', ''),
        homepage=data.get('homepage', ''),
        run_command='npx',
        run_args=['-y', data.get('name', package_name)],
        env_vars=env_vars,
        requires_credentials=requires_creds,
    )


def _resolve_npm_url(url: str) -> ResolvedPackage:
    name = _extract_npm_package_name(url)
    return _fetch_npm_metadata(name)


# ── PyPI ─────────────────────────────────────────────────────────────

def _extract_pypi_package_name(url: str) -> str:
    """Extract package name from pypi.org URL."""
    # https://pypi.org/project/mcp-server-fetch/
    path = urlparse(url).path
    match = re.match(r'^/project/([^/]+)', path)
    if not match:
        raise ResolutionError(f'Cannot parse PyPI package name from: {url}')
    return match.group(1)


def _fetch_pypi_metadata(package_name: str) -> ResolvedPackage:
    """Fetch package metadata from PyPI JSON API."""
    api_url = f'https://pypi.org/pypi/{package_name}/json'
    resp = httpx.get(api_url)
    if resp.status_code != 200:
        raise ResolutionError(f'PyPI package not found: {package_name}')

    info = resp.json().get('info', {})
    readme = info.get('description', '')
    requires_creds, env_vars = _detect_credentials(readme)

    # Convert package name to module: mcp-server-fetch -> mcp_server_fetch
    module_name = info.get('name', package_name).replace('-', '_')

    return ResolvedPackage(
        package_name=info.get('name', package_name),
        package_type='pypi',
        version=info.get('version', ''),
        description=info.get('summary', ''),
        homepage=info.get('home_page', ''),
        run_command='python',
        run_args=['-m', module_name],
        env_vars=env_vars,
        requires_credentials=requires_creds,
    )


def _resolve_pypi_url(url: str) -> ResolvedPackage:
    name = _extract_pypi_package_name(url)
    return _fetch_pypi_metadata(name)


# ── mcpservers.org ───────────────────────────────────────────────────

def _resolve_mcpservers_org(url: str) -> ResolvedPackage:
    """Parse mcpservers.org catalog page, find npm/pypi link, delegate."""
    resp = httpx.get(url)
    if resp.status_code != 200:
        raise ResolutionError(f'Cannot fetch catalog page: {url}')

    html = resp.text

    # Look for npmjs.com link
    npm_match = re.search(r'href=["\']?(https://(?:www\.)?npmjs\.com/package/[^"\'>\s]+)', html)
    if npm_match:
        return _resolve_npm_url(npm_match.group(1))

    # Look for pypi.org link
    pypi_match = re.search(r'href=["\']?(https://pypi\.org/project/[^"\'>\s]+)', html)
    if pypi_match:
        return _resolve_pypi_url(pypi_match.group(1))

    raise ResolutionError(
        'Could not find npm or PyPI package link on the catalog page. '
        'Try pasting the npmjs.com or pypi.org URL directly.'
    )


# ── GitHub ───────────────────────────────────────────────────────────

def _resolve_github(url: str) -> ResolvedPackage:
    """Check GitHub repo for package.json or pyproject.toml, delegate."""
    parsed = urlparse(url)
    path_parts = parsed.path.strip('/').split('/')
    if len(path_parts) < 2:
        raise ResolutionError(f'Invalid GitHub URL: {url}')

    owner, repo = path_parts[0], path_parts[1]

    # Try package.json first (npm)
    raw_url = f'https://raw.githubusercontent.com/{owner}/{repo}/main/package.json'
    resp = httpx.get(raw_url)
    if resp.status_code == 200:
        data = resp.json()
        pkg_name = data.get('name', repo)
        return _fetch_npm_metadata(pkg_name)

    # Try pyproject.toml (python) — just use repo name as pypi package
    raw_url = f'https://raw.githubusercontent.com/{owner}/{repo}/main/pyproject.toml'
    resp = httpx.get(raw_url)
    if resp.status_code == 200:
        return _fetch_pypi_metadata(repo)

    raise ResolutionError(
        f'Cannot detect package type for GitHub repo {owner}/{repo}. '
        'No package.json or pyproject.toml found on main branch.'
    )


# ── Direct name ──────────────────────────────────────────────────────

def _resolve_direct_name(name: str) -> ResolvedPackage:
    """Try npm registry first, then PyPI."""
    # Try npm
    try:
        return _fetch_npm_metadata(name)
    except ResolutionError:
        pass

    # Try PyPI
    try:
        return _fetch_pypi_metadata(name)
    except ResolutionError:
        pass

    raise ResolutionError(
        f'Package "{name}" not found on npm or PyPI.'
    )
```

- [ ] **Step 4: Run tests**

```bash
cd /home/dchuprina/jeevs/backend
docker compose exec web python -m pytest Jeeves/tools/tests/test_resolvers.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/Jeeves/tools/resolvers.py backend/Jeeves/tools/tests/
git commit -m "feat(tools): add URL resolver chain for npm/pypi/mcpservers.org/github"
```

---

### Task 3: Package Installer + Stdio Discovery

**Files:**
- Create: `backend/Jeeves/tools/installer.py`
- Create: `backend/Jeeves/tools/tests/test_installer.py`

- [ ] **Step 1: Write tests for installer**

Create `backend/Jeeves/tools/tests/test_installer.py`:

```python
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

from Jeeves.tools.resolvers import ResolvedPackage
from Jeeves.tools.installer import install_package, uninstall_package, discover_stdio_tools


class TestInstallPackage:
    @patch('Jeeves.tools.installer.subprocess')
    def test_install_npm(self, mock_subprocess):
        mock_subprocess.run.return_value = MagicMock(returncode=0, stdout='', stderr='')

        pkg = ResolvedPackage(
            package_name='mcp-calendar',
            package_type='npm',
            run_command='npx',
            run_args=['-y', 'mcp-calendar'],
        )

        install_package(pkg)

        mock_subprocess.run.assert_called_once()
        args = mock_subprocess.run.call_args
        assert 'npm' in args[0][0][0]
        assert 'install' in args[0][0]
        assert 'mcp-calendar' in args[0][0]

    @patch('Jeeves.tools.installer.subprocess')
    def test_install_pypi(self, mock_subprocess):
        mock_subprocess.run.return_value = MagicMock(returncode=0, stdout='', stderr='')

        pkg = ResolvedPackage(
            package_name='mcp-server-fetch',
            package_type='pypi',
            run_command='python',
            run_args=['-m', 'mcp_server_fetch'],
        )

        install_package(pkg)

        mock_subprocess.run.assert_called_once()
        args = mock_subprocess.run.call_args
        assert 'pip' in args[0][0][0]
        assert 'install' in args[0][0]

    @patch('Jeeves.tools.installer.subprocess')
    def test_install_failure_raises(self, mock_subprocess):
        mock_subprocess.run.return_value = MagicMock(
            returncode=1, stdout='', stderr='Package not found',
        )

        pkg = ResolvedPackage(
            package_name='nonexistent',
            package_type='npm',
            run_command='npx',
            run_args=['-y', 'nonexistent'],
        )

        from Jeeves.tools.installer import InstallError
        with pytest.raises(InstallError, match='Package not found'):
            install_package(pkg)


class TestUninstallPackage:
    @patch('Jeeves.tools.installer.subprocess')
    def test_uninstall_npm(self, mock_subprocess):
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        uninstall_package('mcp-calendar', 'npm')
        args = mock_subprocess.run.call_args
        assert 'uninstall' in args[0][0]

    @patch('Jeeves.tools.installer.subprocess')
    def test_uninstall_pypi(self, mock_subprocess):
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        uninstall_package('mcp-server-fetch', 'pypi')
        args = mock_subprocess.run.call_args
        assert 'uninstall' in args[0][0]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/dchuprina/jeevs/backend
docker compose exec web python -m pytest Jeeves/tools/tests/test_installer.py -v 2>&1 | head -20
```

Expected: ImportError.

- [ ] **Step 3: Implement installer**

Create `backend/Jeeves/tools/installer.py`:

```python
import asyncio
import logging
import os
import subprocess

from .resolvers import ResolvedPackage

logger = logging.getLogger(__name__)

DISCOVERY_TIMEOUT = 15  # seconds


class InstallError(Exception):
    pass


def install_package(pkg: ResolvedPackage) -> None:
    """Install an npm or pypi package globally."""
    if pkg.package_type == 'npm':
        cmd = ['npm', 'install', '-g', pkg.package_name]
    elif pkg.package_type == 'pypi':
        cmd = ['pip', 'install', pkg.package_name]
    else:
        raise InstallError(f'Unsupported package type: {pkg.package_type}')

    logger.info('Installing %s package: %s', pkg.package_type, pkg.package_name)

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=120,
    )

    if result.returncode != 0:
        error_msg = result.stderr.strip() or result.stdout.strip() or 'Unknown error'
        raise InstallError(error_msg)

    logger.info('Successfully installed %s', pkg.package_name)


def uninstall_package(package_name: str, package_type: str) -> None:
    """Uninstall an npm or pypi package."""
    if package_type == 'npm':
        cmd = ['npm', 'uninstall', '-g', package_name]
    elif package_type == 'pypi':
        cmd = ['pip', 'uninstall', '-y', package_name]
    else:
        return

    logger.info('Uninstalling %s package: %s', package_type, package_name)
    subprocess.run(cmd, capture_output=True, text=True, timeout=60)


async def _discover_stdio(
    run_command: str,
    run_args: list,
    env_config: dict | None = None,
) -> list[dict]:
    """Start MCP server via stdio, call list_tools(), return tool schemas."""
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters

    env = {**os.environ}
    # Don't leak Django secrets to subprocess
    for key in ('SECRET_KEY', 'DATABASE_URL'):
        env.pop(key, None)
    if env_config:
        env.update(env_config)

    params = StdioServerParameters(
        command=run_command,
        args=run_args,
        env=env,
    )

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.list_tools()
            return [
                {
                    'name': t.name,
                    'description': t.description or '',
                    'inputSchema': t.inputSchema if hasattr(t, 'inputSchema') else {},
                }
                for t in result.tools
            ]


def discover_stdio_tools(
    run_command: str,
    run_args: list,
    env_config: dict | None = None,
) -> list[dict]:
    """Synchronous wrapper for stdio tool discovery."""
    try:
        tools = asyncio.run(
            asyncio.wait_for(
                _discover_stdio(run_command, run_args, env_config),
                timeout=DISCOVERY_TIMEOUT,
            )
        )
        if not tools:
            raise InstallError('Server returned zero tools.')
        return tools
    except InstallError:
        raise
    except asyncio.TimeoutError:
        raise InstallError(f'Server did not respond within {DISCOVERY_TIMEOUT}s.')
    except Exception as e:
        raise InstallError(f'Failed to discover tools: {e}')
```

- [ ] **Step 4: Run tests**

```bash
cd /home/dchuprina/jeevs/backend
docker compose exec web python -m pytest Jeeves/tools/tests/test_installer.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/Jeeves/tools/installer.py backend/Jeeves/tools/tests/test_installer.py
git commit -m "feat(tools): add package installer and stdio tool discovery"
```

---

### Task 4: Update Discovery Flow (Views + Serializers)

**Files:**
- Modify: `backend/Jeeves/tools/mcp_discovery.py`
- Modify: `backend/Jeeves/tools/views_owner.py`
- Modify: `backend/Jeeves/tools/serializers_owner.py`

- [ ] **Step 1: Update mcp_discovery.py to support URL resolution**

Replace the `discover_mcp_server` function in `backend/Jeeves/tools/mcp_discovery.py` to try URL resolution first, then fall back to SSE:

```python
# backend/Jeeves/tools/mcp_discovery.py
import asyncio
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DISCOVERY_TIMEOUT = 10  # seconds


@dataclass
class DiscoveryResult:
    server_name: str
    tools: list  # [{"name": ..., "description": ..., "inputSchema": ...}]
    # Package resolution data (None for SSE servers)
    resolved_package: object | None = None


class DiscoveryError(Exception):
    pass


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
            return DiscoveryResult(server_name=server_name, tools=tools)


def discover_mcp_server(url: str) -> DiscoveryResult:
    """Resolve URL to package info + discover tools.

    Tries URL resolution (npm/pypi/catalog) first.
    Falls back to SSE discovery for direct MCP server URLs.
    Raises DiscoveryError on any failure.
    """
    from .resolvers import resolve_url, ResolutionError
    from .installer import discover_stdio_tools, InstallError, install_package

    # 1. Try URL resolution (npm, pypi, mcpservers.org, github, name)
    try:
        resolved = resolve_url(url)
    except ResolutionError:
        resolved = None

    if resolved:
        # Install the package so we can discover tools via stdio
        try:
            install_package(resolved)
        except InstallError as e:
            raise DiscoveryError(f'Install failed: {e}')

        try:
            tools = discover_stdio_tools(
                resolved.run_command, resolved.run_args,
            )
        except InstallError as e:
            raise DiscoveryError(f'Tool discovery failed: {e}')

        return DiscoveryResult(
            server_name=resolved.package_name,
            tools=tools,
            resolved_package=resolved,
        )

    # 2. Fallback: try SSE (direct MCP server URL)
    try:
        result = asyncio.run(
            asyncio.wait_for(_discover_sse(url), timeout=DISCOVERY_TIMEOUT)
        )
        if not result.tools:
            raise DiscoveryError("Server returned zero tools.")
        return result
    except DiscoveryError:
        raise
    except asyncio.TimeoutError:
        raise DiscoveryError(f"Connection timed out after {DISCOVERY_TIMEOUT}s.")
    except Exception as e:
        raise DiscoveryError(f"Failed to connect: {e}")
```

- [ ] **Step 2: Update serializers to include resolved package data and client selection**

In `backend/Jeeves/tools/serializers_owner.py`, update `DiscoverRequestSerializer` to accept URL or name, and update `FromUrlRequestSerializer` to include credentials and client IDs:

```python
from django.utils.text import slugify
from rest_framework import serializers

from .models import ToolCard, InstalledMCPServer


class ToolCardOwnerSerializer(serializers.ModelSerializer):
    connections_count = serializers.IntegerField(read_only=True, default=0)
    tools_count = serializers.SerializerMethodField()
    installed_server = serializers.SerializerMethodField()

    class Meta:
        model = ToolCard
        fields = [
            'id', 'name', 'slug', 'tagline', 'tagline_i18n', 'description',
            'icon', 'color', 'category',
            'mcp_server_url', 'transport_type', 'is_builtin', 'builtin_handler',
            'tools_schema', 'scope_schema', 'skill_scopes',
            'auth_type', 'auth_config',
            'is_active', 'is_featured', 'is_system',
            'sort_order',
            'connections_count', 'tools_count', 'installed_server',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'connections_count', 'tools_count', 'installed_server',
            'created_at', 'updated_at',
        ]

    def get_tools_count(self, obj):
        schema = obj.tools_schema
        if isinstance(schema, list):
            return len(schema)
        return 0

    def get_installed_server(self, obj):
        try:
            srv = obj.installed_server
        except InstalledMCPServer.DoesNotExist:
            return None
        return {
            'package_name': srv.package_name,
            'package_type': srv.package_type,
            'version': srv.version,
            'status': srv.status,
            'source_url': srv.source_url,
            'installed_at': srv.installed_at,
            'requires_credentials': bool(srv.env_config),
        }

    def validate_slug(self, value):
        return value

    def create(self, validated_data):
        if not validated_data.get('slug'):
            base = slugify(validated_data.get('name', ''))
            slug = base
            counter = 2
            while ToolCard.objects.filter(slug=slug).exists():
                slug = f"{base}-{counter}"
                counter += 1
            validated_data['slug'] = slug
        return super().create(validated_data)


class DiscoverRequestSerializer(serializers.Serializer):
    url = serializers.CharField(help_text='URL or package name')


class FromUrlRequestSerializer(serializers.Serializer):
    url = serializers.CharField()
    name = serializers.CharField(max_length=100, required=False, default='')
    icon = serializers.CharField(max_length=50, required=False, default='puzzle')
    color = serializers.CharField(max_length=7, required=False, default='#6366f1')
    category = serializers.ChoiceField(
        choices=ToolCard.CATEGORY_CHOICES, required=False, default='custom',
    )
    targets = serializers.ListField(
        child=serializers.ChoiceField(choices=['assistant', 'manager', 'leads']),
        required=False, default=['assistant'],
    )
    client_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False, default=[],
        help_text='Client IDs to connect this server to',
    )
    credentials = serializers.DictField(
        required=False, default={},
        help_text='Environment variables for the MCP server (e.g. API keys)',
    )
```

- [ ] **Step 3: Update views to use resolvers and create InstalledMCPServer**

Rewrite `backend/Jeeves/tools/views_owner.py`:

```python
import logging

from django.db.models import Count
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from Jeeves.clients.models import Client
from Jeeves.concierge_platform.permissions import IsOwner
from .models import ToolCard, ToolConnection, InstalledMCPServer
from .mcp_discovery import discover_mcp_server, DiscoveryError
from .installer import uninstall_package, InstallError
from .serializers_owner import (
    ToolCardOwnerSerializer,
    DiscoverRequestSerializer,
    FromUrlRequestSerializer,
)

logger = logging.getLogger(__name__)


class ToolCardOwnerViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsOwner]
    serializer_class = ToolCardOwnerSerializer

    def get_queryset(self):
        return ToolCard.objects.annotate(
            connections_count=Count('connections'),
        ).select_related('installed_server').order_by('sort_order', 'name')

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_builtin:
            return Response(
                {'error': 'Cannot delete built-in tools.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Uninstall package if it was auto-installed
        try:
            srv = instance.installed_server
            uninstall_package(srv.package_name, srv.package_type)
        except (InstalledMCPServer.DoesNotExist, InstallError):
            pass
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'])
    def discover(self, request):
        """Resolve URL/name, install package, return available tools."""
        ser = DiscoverRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        url = ser.validated_data['url']

        # Check for duplicate
        existing = InstalledMCPServer.objects.filter(
            source_url=url, status='installed',
        ).first()
        if existing:
            return Response(
                {'error': f'Already installed: {existing.package_name}'},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            result = discover_mcp_server(url)
        except DiscoveryError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_data = {
            'server_name': result.server_name,
            'tools': result.tools,
        }

        # Include package resolution data if available
        if result.resolved_package:
            pkg = result.resolved_package
            response_data['package'] = {
                'package_name': pkg.package_name,
                'package_type': pkg.package_type,
                'version': pkg.version,
                'description': pkg.description,
                'requires_credentials': pkg.requires_credentials,
                'env_vars': pkg.env_vars,
            }

        return Response(response_data)

    @action(detail=False, methods=['post'], url_path='from-url')
    def from_url(self, request):
        """Discover + create ToolCard + InstalledMCPServer + connect to selected clients."""
        ser = FromUrlRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        # 1. Discover
        try:
            result = discover_mcp_server(data['url'])
        except DiscoveryError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Create ToolCard
        name = data['name'] or result.server_name or 'Unnamed MCP Server'
        is_stdio = result.resolved_package is not None

        tool_data = {
            'name': name,
            'tagline': f"MCP server with {len(result.tools)} tools",
            'description': ', '.join(t['name'] for t in result.tools),
            'icon': data['icon'],
            'color': data['color'],
            'category': data['category'],
            'mcp_server_url': '' if is_stdio else data['url'],
            'transport_type': 'stdio' if is_stdio else 'sse',
            'is_builtin': False,
            'tools_schema': result.tools,
            'auth_type': 'none',
            'is_active': True,
            'is_system': False,
            'skill_scopes': {'scopes': data['targets']},
        }
        card_ser = ToolCardOwnerSerializer(data=tool_data)
        card_ser.is_valid(raise_exception=True)
        tool_card = card_ser.save()

        # 3. Create InstalledMCPServer if package-based
        if is_stdio and result.resolved_package:
            pkg = result.resolved_package
            InstalledMCPServer.objects.create(
                tool_card=tool_card,
                package_name=pkg.package_name,
                package_type=pkg.package_type,
                version=pkg.version,
                run_command=pkg.run_command,
                run_args=pkg.run_args,
                env_config=data.get('credentials', {}),
                source_url=data['url'],
                status='installed',
            )

        # 4. Connect to selected clients (not all)
        client_ids = data.get('client_ids', [])
        if client_ids:
            now = timezone.now()
            clients = Client.objects.filter(id__in=client_ids)
            connections = []
            for client in clients:
                for target in data['targets']:
                    connections.append(ToolConnection(
                        client=client,
                        tool_card=tool_card,
                        target=target,
                        status='connected',
                        enabled=True,
                        connected_at=now,
                    ))
            ToolConnection.objects.bulk_create(connections, ignore_conflicts=True)

        # Re-fetch with annotation
        tool_card = self.get_queryset().get(pk=tool_card.pk)
        return Response(
            ToolCardOwnerSerializer(tool_card).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def refresh(self, request, pk=None):
        """Re-discover tools from existing MCP server."""
        tool_card = self.get_object()

        # For stdio servers, use installer discovery
        try:
            srv = tool_card.installed_server
            from .installer import discover_stdio_tools
            tools = discover_stdio_tools(
                srv.run_command, srv.run_args, srv.env_config or None,
            )
            tool_card.tools_schema = tools
            tool_card.save(update_fields=['tools_schema', 'updated_at'])
            tool_card = self.get_queryset().get(pk=tool_card.pk)
            return Response(ToolCardOwnerSerializer(tool_card).data)
        except InstalledMCPServer.DoesNotExist:
            pass

        # For SSE servers, use existing flow
        if not tool_card.mcp_server_url:
            return Response(
                {'error': 'No MCP server URL configured.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = discover_mcp_server(tool_card.mcp_server_url)
        except DiscoveryError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tool_card.tools_schema = result.tools
        tool_card.save(update_fields=['tools_schema', 'updated_at'])
        tool_card = self.get_queryset().get(pk=tool_card.pk)
        return Response(ToolCardOwnerSerializer(tool_card).data)
```

- [ ] **Step 4: Run existing tests to make sure nothing is broken**

```bash
cd /home/dchuprina/jeevs/backend
docker compose exec web python -m pytest Jeeves/ -v --tb=short 2>&1 | tail -20
```

Expected: all existing tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/Jeeves/tools/mcp_discovery.py backend/Jeeves/tools/views_owner.py backend/Jeeves/tools/serializers_owner.py
git commit -m "feat(tools): update discover/install flow for URL resolution and stdio servers"
```

---

### Task 5: Orchestrator Integration

**Files:**
- Modify: `backend/Jeeves/agents/orchestrator.py`

- [ ] **Step 1: Extend orchestrator.connect() to include InstalledMCPServer entries**

In `backend/Jeeves/agents/orchestrator.py`, modify the `connect()` method. After the existing loop over `settings.MCP_SERVERS`, add a second loop for installed servers:

```python
async def connect(self) -> None:
    """Spawn enabled MCP servers and discover their tools."""
    server_defs: dict[str, dict] = getattr(settings, "MCP_SERVERS", {})

    self._exit_stack = AsyncExitStack()
    await self._exit_stack.__aenter__()

    env = self._build_subprocess_env()

    # 1. Built-in servers from settings
    for name, cfg in server_defs.items():
        if not cfg.get("enabled", True):
            continue

        params = StdioServerParameters(
            command=cfg["command"],
            args=cfg.get("args", []),
            env=env,
        )

        try:
            transport = await self._exit_stack.enter_async_context(
                stdio_client(params),
            )
            read_stream, write_stream = transport
            session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream),
            )
            await session.initialize()
            self._sessions[name] = session

            result = await session.list_tools()
            for tool in result.tools:
                self._tools.append(tool)
                self._tool_to_server[tool.name] = name

            logger.info(
                "MCP server '%s' connected — %d tool(s): %s",
                name,
                len(result.tools),
                [t.name for t in result.tools],
            )

        except Exception:
            logger.exception("Failed to connect MCP server '%s'", name)

    # 2. Dynamically installed servers from DB
    await self._connect_installed_servers(env)
```

Add the new method to the class:

```python
async def _connect_installed_servers(self, env: dict) -> None:
    """Connect to MCP servers installed via the owner admin."""
    from Jeeves.tools.models import InstalledMCPServer

    servers = InstalledMCPServer.objects.filter(
        status='installed', tool_card__is_active=True,
    ).select_related('tool_card')

    async for srv in servers:
        name = srv.tool_card.slug

        if name in self._sessions:
            continue  # Skip duplicates

        # Build env: base env + server-specific credentials
        server_env = {**env}
        if srv.env_config:
            server_env.update(srv.env_config)

        params = StdioServerParameters(
            command=srv.run_command,
            args=srv.run_args or [],
            env=server_env,
        )

        try:
            transport = await self._exit_stack.enter_async_context(
                stdio_client(params),
            )
            read_stream, write_stream = transport
            session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream),
            )
            await session.initialize()
            self._sessions[name] = session

            result = await session.list_tools()
            for tool in result.tools:
                self._tools.append(tool)
                self._tool_to_server[tool.name] = name

            logger.info(
                "Installed MCP server '%s' (%s) connected — %d tool(s)",
                name, srv.package_name, len(result.tools),
            )

        except Exception:
            logger.exception(
                "Failed to connect installed MCP server '%s' (%s)",
                name, srv.package_name,
            )
```

- [ ] **Step 2: Verify orchestrator still imports cleanly**

```bash
cd /home/dchuprina/jeevs/backend
docker compose exec web python -c "from Jeeves.agents.orchestrator import AgentOrchestrator; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/Jeeves/agents/orchestrator.py
git commit -m "feat(orchestrator): load dynamically installed MCP servers from DB"
```

---

### Task 6: Frontend — Update MCPServerEditPage

**Files:**
- Modify: `frontend/src/pages/owner/MCPServerEditPage.jsx`
- Modify: `frontend/src/api/owner.js`

- [ ] **Step 1: Update API client to pass credentials and client_ids**

In `frontend/src/api/owner.js`, the `mcpServersAPI.createFromUrl` already sends the right shape. Add a `choices` endpoint:

```javascript
export const mcpServersAPI = {
  list: () => api.get('/owner/tools/'),
  detail: (id) => api.get(`/owner/tools/${id}/`),
  create: (data) => api.post('/owner/tools/', data),
  update: (id, data) => api.put(`/owner/tools/${id}/`, data),
  delete: (id) => api.delete(`/owner/tools/${id}/`),
  discover: (url) => api.post('/owner/tools/discover/', { url }),
  createFromUrl: (data) => api.post('/owner/tools/from-url/', data),
  refresh: (id) => api.post(`/owner/tools/${id}/refresh/`),
  choices: () => api.get('/owner/clients/choices/'),
};
```

- [ ] **Step 2: Update MCPServerEditPage with credentials form and client selection**

Replace `frontend/src/pages/owner/MCPServerEditPage.jsx` with:

```jsx
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { mcpServersAPI, clientsAPI } from '../../api/owner';

const CATEGORIES = [
  { value: 'communication', label: 'Communication' },
  { value: 'productivity', label: 'Productivity' },
  { value: 'analytics', label: 'Analytics' },
  { value: 'ai', label: 'AI & Knowledge' },
  { value: 'crm', label: 'CRM & Sales' },
  { value: 'custom', label: 'Custom' },
];

const TARGETS = [
  { value: 'assistant', label: 'AI Assistant' },
  { value: 'manager', label: 'Client Manager' },
  { value: 'leads', label: 'Leads' },
];

const buttonClass =
  'px-4 py-2 bg-ink text-cream rounded-sm hover:bg-ink/90 disabled:opacity-50 text-sm';
const secondaryClass =
  'px-4 py-2 border border-ink/20 rounded-sm hover:bg-ink/5 disabled:opacity-50 text-sm';
const inputClass =
  'w-full px-3 py-2 border border-ink/20 rounded-sm bg-cream text-ink text-sm';

const Field = ({ label, children, error }) => (
  <label className="block space-y-1">
    <span className="text-xs label-mono text-ink/60">{label}</span>
    {children}
    {error && <p className="text-xs text-red-600">{String(error)}</p>}
  </label>
);

const MCPServerEditPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEdit = id && id !== 'new';

  // Discovery state
  const [url, setUrl] = useState('');
  const [discovering, setDiscovering] = useState(false);
  const [discovered, setDiscovered] = useState(null);
  const [discoverError, setDiscoverError] = useState('');

  // Form state
  const [form, setForm] = useState({
    name: '',
    icon: 'puzzle',
    color: '#6366f1',
    category: 'custom',
    targets: ['assistant'],
  });
  const [credentials, setCredentials] = useState({});
  const [selectedClients, setSelectedClients] = useState([]);
  const [clients, setClients] = useState([]);
  const [existing, setExisting] = useState(null);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState({});

  // Load clients list
  useEffect(() => {
    clientsAPI.list().then(({ data }) => {
      const list = Array.isArray(data) ? data : data.results || [];
      setClients(list);
    });
  }, []);

  // Load existing server data in edit mode
  useEffect(() => {
    if (!isEdit) return;
    mcpServersAPI.detail(id).then(({ data }) => {
      setExisting(data);
      setForm({
        name: data.name || '',
        icon: data.icon || 'puzzle',
        color: data.color || '#6366f1',
        category: data.category || 'custom',
        targets: data.skill_scopes?.scopes || ['assistant'],
      });
      setDiscovered({ server_name: data.name, tools: data.tools_schema || [] });
    });
  }, [id, isEdit]);

  const set = (field, value) => setForm((f) => ({ ...f, [field]: value }));

  const toggleTarget = (target) => {
    setForm((f) => {
      const targets = f.targets.includes(target)
        ? f.targets.filter((t) => t !== target)
        : [...f.targets, target];
      return { ...f, targets: targets.length ? targets : f.targets };
    });
  };

  const toggleClient = (clientId) => {
    setSelectedClients((prev) =>
      prev.includes(clientId)
        ? prev.filter((c) => c !== clientId)
        : [...prev, clientId]
    );
  };

  const setCredential = (key, value) => {
    setCredentials((prev) => ({ ...prev, [key]: value }));
  };

  const handleDiscover = async () => {
    setDiscovering(true);
    setDiscoverError('');
    setDiscovered(null);
    try {
      const { data } = await mcpServersAPI.discover(url);
      setDiscovered(data);
      if (data.server_name && !form.name) {
        set('name', data.server_name);
      }
      // Pre-fill credential fields if detected
      if (data.package?.env_vars) {
        const creds = {};
        data.package.env_vars.forEach((v) => { creds[v] = ''; });
        setCredentials(creds);
      }
    } catch (e) {
      const errMsg = e?.response?.data?.error || 'Discovery failed';
      setDiscoverError(errMsg);
    } finally {
      setDiscovering(false);
    }
  };

  const handleSave = async () => {
    setBusy(true);
    setErrors({});
    try {
      if (isEdit) {
        await mcpServersAPI.update(id, {
          name: form.name,
          icon: form.icon,
          color: form.color,
          category: form.category,
          skill_scopes: { scopes: form.targets },
        });
      } else {
        await mcpServersAPI.createFromUrl({
          url,
          name: form.name,
          icon: form.icon,
          color: form.color,
          category: form.category,
          targets: form.targets,
          client_ids: selectedClients,
          credentials,
        });
      }
      navigate('/owner/mcp-servers');
    } catch (e) {
      setErrors(e?.response?.data || { detail: 'Save failed' });
    } finally {
      setBusy(false);
    }
  };

  const handleRefresh = async () => {
    setBusy(true);
    try {
      const { data } = await mcpServersAPI.refresh(id);
      setDiscovered({ server_name: data.name, tools: data.tools_schema || [] });
      setExisting(data);
    } catch (e) {
      alert(e?.response?.data?.error || 'Refresh failed');
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Delete "${form.name}"?`)) return;
    try {
      await mcpServersAPI.delete(id);
      navigate('/owner/mcp-servers');
    } catch (e) {
      alert(e?.response?.data?.error || 'Delete failed');
    }
  };

  const envVars = Object.keys(credentials);
  const hasCredentials = envVars.length > 0;

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-semibold text-ink">
        {isEdit ? `Edit ${existing?.name || ''}` : 'Add MCP Server'}
      </h1>

      {/* Discovery section — only for new */}
      {!isEdit && (
        <div className="space-y-3 p-4 border border-ink/10 rounded-sm">
          <Field label="URL or package name">
            <div className="flex gap-2">
              <input
                className={inputClass}
                placeholder="https://mcpservers.org/... or mcp-package-name"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
              <button
                className={secondaryClass}
                onClick={handleDiscover}
                disabled={discovering || !url}
              >
                {discovering ? 'Discovering...' : 'Discover'}
              </button>
            </div>
          </Field>
          <p className="text-xs text-ink/40">
            Supports: mcpservers.org, npmjs.com, pypi.org, GitHub, or a package name
          </p>
          {discoverError && (
            <p className="text-sm text-red-600">{discoverError}</p>
          )}
        </div>
      )}

      {/* Package info banner */}
      {discovered?.package && (
        <div className="p-3 bg-ink/[0.03] border border-ink/10 rounded-sm text-sm space-y-1">
          <div className="flex items-center gap-2">
            <span className="font-mono font-medium">{discovered.package.package_name}</span>
            <span className="text-xs bg-ink/10 px-1.5 py-0.5 rounded-sm">
              {discovered.package.package_type}
            </span>
            {discovered.package.version && (
              <span className="text-xs text-ink/50">v{discovered.package.version}</span>
            )}
          </div>
          {discovered.package.description && (
            <p className="text-ink/60">{discovered.package.description}</p>
          )}
        </div>
      )}

      {/* Discovered tools preview */}
      {discovered && (
        <div className="space-y-3">
          <div className="p-4 border border-ink/10 rounded-sm bg-ink/[0.02]">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-ink">
                Available Tools ({discovered.tools.length})
              </h3>
              {isEdit && !existing?.is_builtin && (
                <button
                  className={secondaryClass}
                  onClick={handleRefresh}
                  disabled={busy}
                >
                  Refresh Tools
                </button>
              )}
            </div>
            <div className="space-y-1">
              {discovered.tools.map((tool, i) => (
                <div key={i} className="text-sm py-1 border-b border-ink/5 last:border-0">
                  <span className="font-mono text-xs text-ink/80">{tool.name}</span>
                  {tool.description && (
                    <span className="ml-2 text-ink/50">{tool.description}</span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Credentials form */}
          {hasCredentials && !isEdit && (
            <div className="p-4 border border-amber-300 bg-amber-50 rounded-sm space-y-3">
              <h3 className="text-sm font-medium text-ink">
                Required credentials
              </h3>
              <p className="text-xs text-ink/60">
                This server needs API keys or tokens to function.
              </p>
              {envVars.map((key) => (
                <Field key={key} label={key}>
                  <input
                    className={inputClass}
                    type="password"
                    placeholder={`Enter ${key}`}
                    value={credentials[key] || ''}
                    onChange={(e) => setCredential(key, e.target.value)}
                  />
                </Field>
              ))}
            </div>
          )}

          {/* Metadata form */}
          <div className="grid grid-cols-2 gap-4">
            <Field label="Name" error={errors.name}>
              <input
                className={inputClass}
                value={form.name}
                onChange={(e) => set('name', e.target.value)}
                disabled={isEdit && existing?.is_builtin}
              />
            </Field>
            <Field label="Category">
              <select
                className={inputClass}
                value={form.category}
                onChange={(e) => set('category', e.target.value)}
              >
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </Field>
            <Field label="Icon (name)">
              <input
                className={inputClass}
                value={form.icon}
                onChange={(e) => set('icon', e.target.value)}
              />
            </Field>
            <Field label="Color">
              <div className="flex gap-2 items-center">
                <input
                  type="color"
                  value={form.color}
                  onChange={(e) => set('color', e.target.value)}
                  className="w-10 h-10 border border-ink/20 rounded-sm cursor-pointer"
                />
                <input
                  className={inputClass}
                  value={form.color}
                  onChange={(e) => set('color', e.target.value)}
                  maxLength={7}
                />
              </div>
            </Field>
          </div>

          {/* Target checkboxes */}
          <div className="space-y-2">
            <span className="text-xs label-mono text-ink/60">Connect to targets</span>
            <div className="flex gap-4">
              {TARGETS.map((t) => (
                <label key={t.value} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={form.targets.includes(t.value)}
                    onChange={() => toggleTarget(t.value)}
                    disabled={isEdit && existing?.is_builtin}
                  />
                  {t.label}
                </label>
              ))}
            </div>
          </div>

          {/* Client selection — only for new */}
          {!isEdit && clients.length > 0 && (
            <div className="space-y-2">
              <span className="text-xs label-mono text-ink/60">
                Assign to clients ({selectedClients.length} selected)
              </span>
              <div className="space-y-1 border border-ink/10 rounded-sm p-3 max-h-60 overflow-y-auto">
                {clients.map((client) => (
                  <label key={client.id} className="flex items-center gap-2 text-sm cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedClients.includes(client.id)}
                      onChange={() => toggleClient(client.id)}
                    />
                    <span>
                      {client.company_name || client.user}
                      {client.tag && (
                        <span className="font-mono text-xs text-ink/50 ml-1">
                          ({client.tag})
                        </span>
                      )}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Installed server info (edit mode) */}
          {isEdit && existing?.installed_server && (
            <div className="p-3 bg-ink/[0.03] border border-ink/10 rounded-sm text-sm">
              <span className="text-xs label-mono text-ink/60 block mb-1">Package</span>
              <span className="font-mono">{existing.installed_server.package_name}</span>
              <span className="text-xs bg-ink/10 px-1.5 py-0.5 rounded-sm ml-2">
                {existing.installed_server.package_type}
              </span>
              <span className="text-xs text-ink/50 ml-2">
                v{existing.installed_server.version}
              </span>
            </div>
          )}

          {/* Errors */}
          {errors.detail && (
            <p className="text-sm text-red-600">{String(errors.detail)}</p>
          )}
          {errors.error && (
            <p className="text-sm text-red-600">{String(errors.error)}</p>
          )}

          {/* Actions */}
          <div className="flex gap-2">
            {!(isEdit && existing?.is_builtin) && (
              <button className={buttonClass} onClick={handleSave} disabled={busy}>
                {isEdit ? 'Save' : 'Install & Connect'}
              </button>
            )}
            <button
              className={secondaryClass}
              onClick={() => navigate('/owner/mcp-servers')}
            >
              {isEdit && existing?.is_builtin ? 'Back' : 'Cancel'}
            </button>
            {isEdit && !existing?.is_builtin && (
              <button
                className="ml-auto px-4 py-2 border border-red-600 text-red-600 rounded-sm text-sm"
                onClick={handleDelete}
              >
                Delete
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default MCPServerEditPage;
```

- [ ] **Step 3: Rebuild frontend and verify**

```bash
cd /home/dchuprina/jeevs/frontend
docker compose up -d --build 2>&1 | tail -5
```

Expected: container rebuilds and starts on port 3000.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/owner/MCPServerEditPage.jsx frontend/src/api/owner.js
git commit -m "feat(frontend): update MCP server page with credentials, client selection, package info"
```

---

### Task 7: Integration Test — End-to-End Flow

**Files:**
- No new files — manual verification

- [ ] **Step 1: Verify the full flow manually**

1. Open http://localhost:3000/owner/mcp-servers
2. Click "Add MCP Server"
3. Paste `https://mcpservers.org/servers/chuprinadaria/mcp-ukrainian-calendar`
4. Click "Discover"
5. Verify: package info, tools list, and metadata form appear
6. Set a name, select clients, click "Install & Connect"
7. Verify: server appears in the list
8. Click Edit on the server, verify details show

- [ ] **Step 2: Run all backend tests**

```bash
cd /home/dchuprina/jeevs/backend
docker compose exec web python -m pytest Jeeves/ -v --tb=short 2>&1 | tail -30
```

Expected: all tests pass.

- [ ] **Step 3: Final commit with any fixes**

```bash
git add -A
git commit -m "feat(mcp): complete MCP auto-deploy integration"
```
