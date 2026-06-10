"""Auto-discover git repositories on PC via SSH.

Supports two config formats:
- Legacy: repos is a dict {name: path} — used directly
- New: repos has scan_dirs + max_depth — auto-discovers via SSH find
"""

import time
from mcp_servers.hardware.utils.config import repos as repos_config
from mcp_servers.hardware.utils.ssh import ssh_run

_cache: dict = {"repos": {}, "ts": 0}
CACHE_TTL = 300  # 5 min


async def discover_repos() -> dict[str, str]:
    """Return {name: path} dict. Cached for 5 min."""
    now = time.time()
    if _cache["repos"] and (now - _cache["ts"]) < CACHE_TTL:
        return _cache["repos"]

    cfg = repos_config()

    # Legacy format: {name: path} dict without scan_dirs key
    if "scan_dirs" not in cfg:
        _cache["repos"] = cfg
        _cache["ts"] = now
        return cfg

    # New format: auto-discover via SSH
    dirs = cfg.get("scan_dirs", ["~/projects"])
    depth = cfg.get("max_depth", 2)

    find_parts = []
    for d in dirs:
        find_parts.append(f"find {d} -maxdepth {depth} -name .git -type d 2>/dev/null")
    cmd = " && ".join(find_parts)

    code, stdout, _ = await ssh_run(cmd, timeout=15)
    if code != 0 or not stdout.strip():
        return _cache.get("repos", {})

    repos = {}
    for line in stdout.strip().splitlines():
        repo_path = line.replace("/.git", "").strip()
        if not repo_path:
            continue
        name = repo_path.rsplit("/", 1)[-1]
        if name not in repos:
            repos[name] = repo_path

    _cache["repos"] = repos
    _cache["ts"] = now
    return repos


def invalidate_cache():
    _cache["ts"] = 0
