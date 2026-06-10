import json

from mcp_servers.hardware.utils.config import pc
from mcp_servers.hardware.utils.network import ping
from mcp_servers.hardware.utils.ssh import ssh_run, ssh_available
from mcp_servers.hardware.utils.discovery import discover_repos


async def pc_status() -> str:
    """Перевіряє стан ПК: online, SSH, uptime, tmux-сесії, доступні проекти."""
    cfg = pc()

    is_online = await ping(cfg["ip"])
    if not is_online:
        return json.dumps({"online": False, "ssh": False}, ensure_ascii=False)

    ssh_ok = await ssh_available()
    if not ssh_ok:
        return json.dumps({"online": True, "ssh": False}, ensure_ascii=False)

    # Uptime
    _, uptime_raw, _ = await ssh_run("uptime -p")
    uptime = uptime_raw.replace("up ", "") if uptime_raw else "unknown"

    # Tmux sessions
    code, tmux_raw, _ = await ssh_run("tmux list-sessions -F '#{session_name}' 2>/dev/null")
    tmux_sessions = tmux_raw.splitlines() if code == 0 and tmux_raw else []

    # VS Code running?
    code, ps_out, _ = await ssh_run("pgrep -f '/usr/share/code/code' > /dev/null && echo yes || echo no")
    vscode_running = ps_out.strip() == "yes"

    # Discover repos
    repos = await discover_repos()

    result = {
        "online": True,
        "ssh": True,
        "uptime": uptime,
        "tmux_sessions": tmux_sessions,
        "vscode_running": vscode_running,
        "repos": list(repos.keys()),
    }
    return json.dumps(result, ensure_ascii=False)
