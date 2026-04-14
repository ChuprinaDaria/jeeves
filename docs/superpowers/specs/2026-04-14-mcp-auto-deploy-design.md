# MCP Auto-Deploy: Owner installs MCP servers from URL

## Summary

Owner pastes a URL (mcpservers.org, npmjs.com, pypi.org, GitHub, or a plain package name) into the owner admin panel. The system resolves the package, installs it, discovers available tools, detects required credentials, and makes the server available for assignment to specific clients.

## Constraints

- Supported package types: npm and Python (pypi)
- Only owner role can add/remove servers
- Servers run as subprocesses inside the existing `concierge_web` container (same pattern as current MCP servers)
- Owner explicitly assigns servers to clients (no auto-connect to all)
- Self-hosted Gumroad product: security and simplicity matter

## 1. URL Resolution Pipeline

Owner submits a URL or package name. The backend runs it through a chain of resolvers until one succeeds:

1. **McpServersOrgResolver** -- URL contains `mcpservers.org/servers/` -- parses the page, extracts link to npmjs.com or pypi.org
2. **NpmResolver** -- URL contains `npmjs.com/package/` or previous step found npm package -- fetches metadata from `registry.npmjs.org/{package}`
3. **PypiResolver** -- URL contains `pypi.org/project/` -- fetches metadata from `pypi.org/pypi/{package}/json`
4. **GitHubResolver** -- URL contains `github.com/` -- fetches repo, checks `package.json` (npm) or `pyproject.toml` (python)
5. **DirectNameResolver** -- plain text like `mcp-ukrainian-calendar` -- tries npm registry first, then PyPI

### Resolver output

```python
ResolvedPackage = {
    "package_name": str,        # "mcp-ukrainian-calendar"
    "package_type": str,        # "npm" | "pypi"
    "version": str,             # "1.0.5"
    "description": str,
    "homepage": str,
    "install_command": str,     # "npm install -g mcp-ukrainian-calendar"
    "run_command": str,         # "mcp-ukrainian-calendar"
    "env_vars": list[str],      # ["API_KEY"] -- detected from README
    "requires_credentials": bool,
}
```

### Credentials detection

The resolver parses README content from npm/pypi metadata, scanning for patterns: `API_KEY`, `TOKEN`, `SECRET`, `CREDENTIALS` in env/config blocks. If found, `requires_credentials=True` and `env_vars` lists the detected variable names.

## 2. Installation & Process Management

### Infrastructure changes

- Add Node.js to the `concierge_web` Dockerfile (multi-stage or runtime install)
- Create a persist-volume for installed packages so they survive container restarts

### Installation flow

- npm: `npm install -g {package}`
- Python: `pip install {package}`

### Discovery flow

1. After install, start server as subprocess via `stdio_client` (existing mechanism)
2. Call `list_tools()` to get tool definitions and schemas
3. Save to `ToolCard.tools_schema`
4. Stop the process (orchestrator starts it on demand later)

### New model: InstalledMCPServer

```python
class InstalledMCPServer(models.Model):
    tool_card = models.OneToOneField(ToolCard, on_delete=models.CASCADE)
    package_name = models.CharField(max_length=255)
    package_type = models.CharField(max_length=10, choices=[("npm", "npm"), ("pypi", "pypi")])
    version = models.CharField(max_length=50)
    run_command = models.CharField(max_length=500)
    run_args = models.JSONField(default=list)
    env_config = EncryptedJSONField(default=dict)  # {"API_KEY": "sk-..."}
    source_url = models.URLField(blank=True)
    installed_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[("installed", "Installed"), ("failed", "Failed"), ("removed", "Removed")],
        default="installed",
    )
    error_message = models.TextField(blank=True)
```

### Credentials flow

If resolver detected required env vars:
1. Frontend shows owner a form with fields for each env var
2. Owner fills in API keys / tokens
3. Saved to `InstalledMCPServer.env_config` (encrypted at rest)
4. Passed as environment variables when spawning the subprocess

## 3. Owner Admin UI

### New pages in owner admin

**Server list** (`/owner/mcp-servers`):
- Table: name, package, type (npm/pypi), status, tool count, install date
- "Add Server" button

**Add server** (`/owner/mcp-servers/add`):
1. Single input field: "Paste URL or package name"
2. Owner pastes URL, clicks "Discover"
3. Backend resolves, returns package info (name, description, type, detected tools)
4. Frontend shows preview
5. If credentials needed, credential input fields appear
6. Owner clicks "Install"
7. Backend installs package, runs discovery, creates ToolCard + InstalledMCPServer
8. After success, owner selects which clients get access (client checkboxes)

**Server detail** (`/owner/mcp-servers/{id}`):
- Package info, version, status
- List of tools from this server (from schema)
- Credentials (masked, editable)
- Connected clients list (add/remove)
- Actions: "Reinstall", "Remove"

Uses existing owner admin patterns: sidebar navigation, `OwnerFormPage`/`OwnerListPage` components.

## 4. Orchestrator Integration

Minimal changes to existing orchestrator.

### `orchestrator.connect()` -- extended

Currently reads `settings.MCP_SERVERS`. After this feature:

1. Read `settings.MCP_SERVERS` -- builtin servers (unchanged)
2. Read `InstalledMCPServer.objects.filter(status='installed')` -- dynamic servers
3. For each dynamic server, create `StdioServerParameters` with `run_command`, `run_args`, and env vars from `env_config`
4. Spawn subprocess, store session -- same as current mechanism

### Scope filtering -- no changes

Already works through `ToolConnection`. Owner creates `ToolConnection` for selected clients when assigning a server. Orchestrator's `_build_scope_filter()` filters by `ToolConnection` as before.

### Tool routing, middleware, logging -- no changes

Dynamic servers produce tools with unique names. Existing `_tool_to_server` mapping handles routing. Middleware pipeline, `AgentLog`, SSE events all work unchanged.

## 5. Security

- `env_config` uses `EncryptedJSONField` (already used in project for `ToolConnection.credentials`)
- Only owner role can install/remove servers (authenticated, role check)
- Subprocess gets only explicitly configured env vars from `env_config` -- no access to Django SECRET_KEY or other host secrets
- Duplicate check by `package_name` before install

## 6. Edge Cases

- **Package not found**: resolver returns error, frontend shows "Package not found, check URL"
- **Install fails**: `InstalledMCPServer.status = 'failed'`, error message saved and displayed
- **Server crashes at startup**: orchestrator catches exception, logs it, other servers continue (existing behavior)
- **Duplicate package**: check by `package_name` before install, show "Already installed"
- **Removal**: `npm uninstall -g` / `pip uninstall -y`, ToolCard deactivated, ToolConnections deleted
- **Container restart**: packages on persist-volume, `InstalledMCPServer` in DB, everything restores automatically

## 7. API Endpoints (new)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/platform/mcp-servers/discover/` | Resolve URL, return package info |
| POST | `/api/platform/mcp-servers/install/` | Install package, create ToolCard |
| GET | `/api/platform/mcp-servers/` | List installed servers |
| GET | `/api/platform/mcp-servers/{id}/` | Server detail |
| PATCH | `/api/platform/mcp-servers/{id}/` | Update credentials, clients |
| POST | `/api/platform/mcp-servers/{id}/reinstall/` | Reinstall package |
| DELETE | `/api/platform/mcp-servers/{id}/` | Uninstall and remove |
| POST | `/api/platform/mcp-servers/{id}/clients/` | Assign to clients |
| DELETE | `/api/platform/mcp-servers/{id}/clients/{client_id}/` | Remove from client |
