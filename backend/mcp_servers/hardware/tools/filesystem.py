"""File system tools — browse, read, write, search. NO delete.

All user-controlled arguments are passed through ``shlex.quote`` before being
inlined into the remote shell command. ``pc_write_file`` streams content via a
base64 pipe instead of a heredoc so a payload containing the terminator can't
break out and execute arbitrary remote commands.
"""

import base64
import shlex

from mcp_servers.hardware.utils.ssh import ssh_run


# Safety: block sensitive paths
_BLOCKED_PATTERNS = (".ssh/", ".gnupg/", ".env", "id_rsa", "id_ed25519", ".secrets")
_MAX_READ_BYTES = 500_000  # ~500KB max read


def _is_safe_path(path: str) -> str | None:
    """Return error message if path is unsafe, None if ok."""
    for pattern in _BLOCKED_PATTERNS:
        if pattern in path:
            return f"Доступ заборонено: шлях містить '{pattern}'"
    return None


async def pc_list_dir(path: str = "~") -> str:
    """Показує вміст директорії на ПК.

    Args:
        path: Шлях до директорії (default: домашня).
    """
    if err := _is_safe_path(path):
        return err

    code, stdout, stderr = await ssh_run(
        f"ls -la --group-directories-first {shlex.quote(path)} 2>&1 | head -100",
        timeout=15,
    )
    if code != 0:
        return f"Помилка: {stderr or stdout}"
    return stdout or "(порожня директорія)"


async def pc_read_file(path: str, offset: int = 0, limit: int = 200) -> str:
    """Читає вміст файлу на ПК.

    Args:
        path: Шлях до файлу.
        offset: Починати з рядка N (0 = з початку).
        limit: Кількість рядків (max 500).
    """
    if err := _is_safe_path(path):
        return err

    limit = min(limit, 500)
    qpath = shlex.quote(path)

    if offset > 0:
        cmd = f"tail -n +{offset + 1} {qpath} | head -n {limit} | cat -n"
    else:
        cmd = f"head -n {limit} {qpath} | cat -n"

    size_code, size_out, _ = await ssh_run(f"stat -c %s {qpath} 2>/dev/null", timeout=10)
    if size_code != 0:
        return f"Файл не знайдено: {path}"

    try:
        file_size = int(size_out)
        if file_size > _MAX_READ_BYTES:
            return f"Файл занадто великий ({file_size} bytes). Використовуй offset/limit."
    except ValueError:
        pass

    code, stdout, stderr = await ssh_run(cmd, timeout=30)
    if code != 0:
        return f"Помилка: {stderr or stdout}"
    return stdout or "(порожній файл)"


async def pc_write_file(path: str, content: str) -> str:
    """Записує вміст у файл на ПК. Створює файл якщо не існує.

    Args:
        path: Шлях до файлу.
        content: Текст для запису.
    """
    if err := _is_safe_path(path):
        return err

    # Stream the file via base64 + pipe — no shell-metachar surface.
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    cmd = f"printf %s {shlex.quote(encoded)} | base64 -d > {shlex.quote(path)}"

    code, stdout, stderr = await ssh_run(cmd, timeout=30)
    if code != 0:
        return f"Помилка запису: {stderr or stdout}"
    return f"Файл записано: {path}"


async def pc_find_files(pattern: str, path: str = "~", max_depth: int = 3) -> str:
    """Шукає файли по патерну (glob) на ПК.

    Args:
        pattern: Патерн пошуку (напр. '*.py', 'docker-compose*').
        path: Де шукати (default: домашня).
        max_depth: Глибина пошуку (default: 3).
    """
    if err := _is_safe_path(path):
        return err

    max_depth = min(max_depth, 5)
    cmd = (
        f"find {shlex.quote(path)} -maxdepth {max_depth} "
        f"-name {shlex.quote(pattern)} -type f 2>/dev/null | head -50"
    )

    code, stdout, stderr = await ssh_run(cmd, timeout=30)
    if code != 0:
        return f"Помилка: {stderr or stdout}"
    return stdout or f"Нічого не знайдено по патерну '{pattern}' в {path}"


async def pc_grep(pattern: str, path: str, glob_filter: str = "") -> str:
    """Шукає текст у файлах на ПК (grep).

    Args:
        pattern: Текст або regex для пошуку.
        path: Файл або директорія де шукати.
        glob_filter: Фільтр файлів (напр. '*.py'). Тільки для директорій.
    """
    if err := _is_safe_path(path):
        return err

    include = f"--include={shlex.quote(glob_filter)}" if glob_filter else ""
    cmd = (
        f"grep -rn {include} -- {shlex.quote(pattern)} {shlex.quote(path)} "
        f"2>/dev/null | head -50"
    )

    code, stdout, stderr = await ssh_run(cmd, timeout=30)
    if code != 0 and not stdout:
        return f"Нічого не знайдено по '{pattern}' в {path}"
    return stdout or "Нічого не знайдено"
