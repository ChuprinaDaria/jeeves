"""System monitoring & control tools — disk, processes, screenshot, clipboard, browser, info."""

import json

from mcp_servers.hardware.utils.ssh import ssh_run


async def pc_disk_usage() -> str:
    """Показує використання диску: загальне + топ проектів по розміру."""
    # Overall disk usage
    code, df_out, _ = await ssh_run("df -h / --output=size,used,avail,pcent | tail -1", timeout=15)
    # Top dirs in home
    _, du_out, _ = await ssh_run(
        "du -sh ~/projects/* ~/Desktop/* 2>/dev/null | sort -rh | head -15",
        timeout=30,
    )
    # Total home size
    _, home_out, _ = await ssh_run("du -sh ~ 2>/dev/null | cut -f1", timeout=30)

    lines = []
    if code == 0 and df_out:
        parts = df_out.split()
        if len(parts) >= 4:
            lines.append(f"Диск: {parts[1]} / {parts[0]} ({parts[3]} зайнято), вільно {parts[2]}")
    if home_out:
        lines.append(f"Домашня папка: {home_out}")
    if du_out:
        lines.append(f"\nТоп по розміру:\n{du_out}")
    return "\n".join(lines) or "Не вдалось отримати дані"


async def pc_processes(sort_by: str = "cpu") -> str:
    """Показує топ процесів по CPU або RAM.

    Args:
        sort_by: 'cpu' або 'mem'.
    """
    if sort_by == "mem":
        cmd = "ps aux --sort=-%mem | head -15"
    else:
        cmd = "ps aux --sort=-%cpu | head -15"

    code, stdout, stderr = await ssh_run(cmd, timeout=15)
    if code != 0:
        return f"Помилка: {stderr or stdout}"
    return stdout


async def pc_screenshot() -> str:
    """Робить скріншот екрану ПК, стягує на Pi і повертає base64.

    Повертає JSON з base64-encoded PNG для відправки в Telegram.
    """
    import base64
    import os

    # Take screenshot on PC
    for tool_cmd in [
        'DISPLAY=:0 gnome-screenshot -f /tmp/screenshot.png 2>&1',
        'DISPLAY=:0 scrot /tmp/screenshot.png 2>&1',
        'DISPLAY=:0 import -window root /tmp/screenshot.png 2>&1',
    ]:
        code, stdout, stderr = await ssh_run(tool_cmd, timeout=15)
        if code == 0:
            # Verify file exists on PC
            vc, size, _ = await ssh_run("stat -c %s /tmp/screenshot.png 2>/dev/null", timeout=5)
            if vc == 0 and size:
                break
    else:
        return "Не вдалось зробити скріншот. Спробуй встановити: sudo apt install gnome-screenshot"

    # Fetch screenshot from PC via SSH (base64 encode on remote, decode locally)
    code, b64_data, stderr = await ssh_run(
        "base64 -w0 /tmp/screenshot.png", timeout=30,
    )
    if code != 0 or not b64_data:
        return f"Скріншот зроблено, але не вдалось стягнути: {stderr}"

    # Save locally on Pi for HTTP serving
    local_path = "/tmp/pi_screenshot.png"
    try:
        raw = base64.b64decode(b64_data)
        with open(local_path, "wb") as f:
            f.write(raw)
        size_kb = len(raw) // 1024
    except Exception as e:
        return f"Помилка декодування скріншоту: {e}"

    return json.dumps({
        "_screenshot_base64": b64_data,
        "message": f"Скріншот зроблено ({size_kb}KB). Відправляю фото.",
    })


async def pc_clipboard_read() -> str:
    """Читає вміст буферу обміну (clipboard) на ПК."""
    code, stdout, stderr = await ssh_run(
        'DISPLAY=:0 xclip -selection clipboard -o 2>/dev/null || '
        'DISPLAY=:0 xsel --clipboard --output 2>/dev/null',
        timeout=10,
    )
    if code != 0 or not stdout:
        return "Буфер обміну порожній або xclip/xsel не встановлено"
    # Limit output
    if len(stdout) > 2000:
        return stdout[:2000] + f"\n... (обрізано, всього {len(stdout)} символів)"
    return stdout


async def pc_clipboard_write(text: str) -> str:
    """Записує текст в буфер обміну (clipboard) на ПК.

    Args:
        text: Текст для копіювання.
    """
    import shlex
    escaped = shlex.quote(text)
    code, _, stderr = await ssh_run(
        f'echo -n {escaped} | DISPLAY=:0 xclip -selection clipboard 2>/dev/null || '
        f'echo -n {escaped} | DISPLAY=:0 xsel --clipboard --input 2>/dev/null',
        timeout=10,
    )
    if code != 0:
        return f"Не вдалось записати в clipboard: {stderr}"
    return f"Скопійовано в буфер обміну ({len(text)} символів)"


async def pc_open_url(url: str) -> str:
    """Відкриває URL у браузері на ПК.

    Args:
        url: URL для відкриття.
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    import shlex
    code, _, stderr = await ssh_run(
        f'DISPLAY=:0 xdg-open {shlex.quote(url)} 2>/dev/null &',
        timeout=10,
    )
    if code != 0:
        return f"Не вдалось відкрити: {stderr}"
    return f"Відкрито в браузері: {url}"


async def pc_system_info() -> str:
    """Повна інформація про систему: CPU, RAM, температура, мережа, uptime."""
    commands = {
        "uptime": "uptime -p",
        "cpu": "lscpu | grep 'Model name' | sed 's/Model name: *//'",
        "cpu_usage": "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1",
        "ram": "free -h | awk '/Mem:/ {printf \"%s / %s (%s used)\", $3, $2, $5}'",
        "temp": "cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | head -1",
        "disk": "df -h / --output=avail,pcent | tail -1",
        "net_ip": "hostname -I | awk '{print $1}'",
        "net_ext": "curl -s --max-time 3 ifconfig.me 2>/dev/null || echo 'N/A'",
        "gpu": "nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null || echo 'N/A'",
        "os": "lsb_release -ds 2>/dev/null || cat /etc/os-release | grep PRETTY_NAME | cut -d'\"' -f2",
        "kernel": "uname -r",
    }

    results = {}
    for key, cmd in commands.items():
        _, stdout, _ = await ssh_run(cmd, timeout=10)
        results[key] = stdout.strip() if stdout else "N/A"

    # Format temperature
    temp = results.get("temp", "N/A")
    if temp != "N/A":
        try:
            temp = f"{int(temp) / 1000:.1f}°C"
        except (ValueError, TypeError):
            pass
    else:
        temp = "датчик недоступний"

    # Format GPU
    gpu = results.get("gpu", "N/A")
    if gpu and gpu != "N/A":
        parts = [p.strip() for p in gpu.split(",")]
        if len(parts) >= 5:
            gpu = f"{parts[0]} | {parts[1]}°C | GPU {parts[2]}% | VRAM {parts[3]}/{parts[4]} MB"

    lines = [
        f"OS: {results['os']} (kernel {results['kernel']})",
        f"CPU: {results['cpu']}",
        f"CPU usage: {results['cpu_usage']}%",
        f"Температура: {temp}",
        f"RAM: {results['ram']}",
        f"Диск вільно: {results['disk'].strip()}",
        f"GPU: {gpu}",
        f"IP: {results['net_ip']} (зовнішній: {results['net_ext']})",
        f"Uptime: {results['uptime']}",
    ]
    return "\n".join(lines)


async def pc_run_safe(command: str) -> str:
    """Виконує безпечну команду на ПК. Тільки з дозволеного списку.

    Args:
        command: Команда (напр. 'git status', 'docker ps', 'npm run build').
    """
    # Whitelist of allowed command prefixes
    allowed = [
        "git ", "docker ps", "docker compose", "docker-compose",
        "npm ", "npx ", "yarn ", "pnpm ", "node ",
        "python ", "python3 ", "pip ", "pip3 ",
        "cat ", "head ", "tail ", "wc ", "sort ",
        "date", "whoami", "hostname", "pwd",
        "systemctl status", "journalctl",
        "htop -n 1", "free", "df",
        "ls ", "tree ",
        "curl ", "wget ",
        "claude ", "tmux ",
    ]

    cmd_lower = command.strip().lower()
    if not any(cmd_lower.startswith(prefix) for prefix in allowed):
        return (
            f"Команда не дозволена: '{command}'\n"
            f"Дозволені: git, docker ps/compose, npm/yarn, python, cat/head/tail, "
            f"systemctl status, ls, tree, curl"
        )

    # Extra safety: block destructive patterns
    dangerous = ["rm ", "rm -", "mkfs", "dd ", "> /dev/", "chmod 777", ":(){ ", "fork"]
    if any(d in cmd_lower for d in dangerous):
        return "Ця команда заблокована з міркувань безпеки."

    # Use login shell for commands that need nvm/node in PATH
    needs_login = any(command.strip().startswith(p) for p in ["claude ", "npm ", "npx ", "node ", "yarn ", "pnpm "])
    code, stdout, stderr = await ssh_run(command, timeout=60, login_shell=needs_login)
    output = stdout or stderr or "(немає виводу)"
    if len(output) > 3000:
        output = output[:3000] + f"\n... (обрізано)"
    if code != 0:
        return f"Exit code {code}:\n{output}"
    return output
