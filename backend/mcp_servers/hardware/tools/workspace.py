import asyncio

from mcp_servers.hardware.utils.config import pc
from mcp_servers.hardware.utils.network import ping
from mcp_servers.hardware.utils.ssh import ssh_run, ssh_available
from mcp_servers.hardware.utils.discovery import discover_repos
from mcp_servers.hardware.tools.wake import pc_wake


async def _find_claude_path() -> str | None:
    """Find claude binary path on remote PC."""
    # Спробувати кілька варіантів де може бути claude
    candidates = [
        # nvm-based node
        'bash -l -c "which claude 2>/dev/null"',
        # Прямий шлях через npm global
        'ls ~/.nvm/versions/node/*/bin/claude 2>/dev/null | tail -1',
        # System-wide
        'which claude 2>/dev/null',
        # npm global без nvm
        'ls /usr/local/bin/claude 2>/dev/null',
        'ls ~/.local/bin/claude 2>/dev/null',
        # npx fallback
        'bash -l -c "which npx 2>/dev/null"',
    ]
    for cmd in candidates:
        code, stdout, _ = await ssh_run(cmd, timeout=10)
        if code == 0 and stdout.strip():
            path = stdout.strip().split('\n')[-1]
            if 'npx' in path:
                return f"{path} @anthropic-ai/claude-code"
            return path
    return None


async def pc_launch_workspace(repo: str) -> str:
    """Запускає Claude remote-control для проєкту в tmux."""
    repo_map = await discover_repos()
    if repo not in repo_map:
        available = ", ".join(repo_map.keys())
        return f"Невідомий репо '{repo}'. Доступні: {available}"

    repo_path = repo_map[repo]
    cfg = pc()

    # Перевірити чи ПК онлайн, якщо ні — розбудити
    if not await ping(cfg["ip"]) or not await ssh_available():
        wake_result = await pc_wake()
        if "не відповідає" in wake_result or "не піднявся" in wake_result:
            return f"Не вдалося увімкнути ПК: {wake_result}"

    # Знайти де claude binary
    claude_path = await _find_claude_path()
    if not claude_path:
        return (
            "claude CLI не знайдено на ПК. "
            "Встанови: npm install -g @anthropic-ai/claude-code"
        )

    session_name = f"claude-rc:{repo}"
    log_file = f"/tmp/claude-rc-{repo}.log"

    # Зупинити попередню сесію цього репо якщо є
    await ssh_run(f"tmux kill-session -t '{session_name}' 2>/dev/null", timeout=5)
    await asyncio.sleep(1)

    # Перевірити tmux
    tmux_code, _, _ = await ssh_run("which tmux", timeout=5)
    if tmux_code != 0:
        await ssh_run("sudo apt-get install -y tmux 2>/dev/null", timeout=30)
        tmux_code, _, _ = await ssh_run("which tmux", timeout=5)
        if tmux_code != 0:
            return "tmux не встановлений. Встанови: sudo apt install tmux"

    # Запустити Claude remote-control в tmux з логом
    code, _, stderr = await ssh_run(
        f"tmux new-session -d -s '{session_name}' '"
        f"cd {repo_path} && "
        f"{claude_path} remote-control --name {repo} --permission-mode default "
        f"2>&1 | tee {log_file}'",
        timeout=10,
    )
    if code != 0:
        return f"tmux не створився: {stderr}"

    # Дати claude час на старт і перевірити що сесія жива
    await asyncio.sleep(5)

    # Перевірка 1: чи tmux сесія ще існує
    sess_code, sess_out, _ = await ssh_run(
        f"tmux has-session -t '{session_name}' 2>/dev/null && echo ALIVE || echo DEAD",
        timeout=5,
    )
    if "DEAD" in sess_out:
        _, log_content, _ = await ssh_run(f"tail -20 {log_file} 2>/dev/null", timeout=5)
        return (
            f"claude remote-control впав одразу після старту.\n"
            f"Лог ({log_file}):\n{log_content or '(порожній)'}"
        )

    # Перевірка 2: чи claude процес працює
    proc_code, proc_out, _ = await ssh_run(
        "pgrep -f 'claude.*remote-control' > /dev/null && echo RUNNING || echo STOPPED",
        timeout=5,
    )
    if "STOPPED" in proc_out:
        _, log_content, _ = await ssh_run(f"tail -20 {log_file} 2>/dev/null", timeout=5)
        return (
            f"tmux сесія є, але claude процес не знайдено.\n"
            f"Лог ({log_file}):\n{log_content or '(порожній)'}"
        )

    # Прочитати перші рядки логу — там буде URL для підключення
    _, log_head, _ = await ssh_run(f"head -10 {log_file} 2>/dev/null", timeout=5)

    return (
        f"Claude remote-control для {repo} працює в tmux '{session_name}'.\n"
        f"Вивід:\n{log_head or '(чекає на підключення)'}"
    )


async def pc_stop_workspace(repo: str | None = None) -> str:
    """Зупиняє workspace — закриває tmux-сесії Claude remote-control."""
    cfg = pc()

    if not await ping(cfg["ip"]) or not await ssh_available():
        return "ПК вимкнений або SSH недоступний."

    if repo:
        session_name = f"claude-rc:{repo}"
        await ssh_run(f"tmux kill-session -t '{session_name}' 2>/dev/null")
        return f"Workspace {repo} зупинений."
    else:
        # Зупинити всі claude-rc сесії
        await ssh_run("tmux kill-server 2>/dev/null", timeout=5)
        return "Всі workspace-и зупинені."
