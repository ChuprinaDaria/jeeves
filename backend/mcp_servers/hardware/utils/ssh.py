import asyncio
import shlex

from mcp_servers.hardware.utils.config import pc


def _shell_quote(s: str) -> str:
    return shlex.quote(s)


async def ssh_run(command: str, timeout: int = 30, login_shell: bool = False) -> tuple[int, str, str]:
    """Run command on PC via SSH. Returns (returncode, stdout, stderr).

    Args:
        command: Shell command to execute.
        timeout: Max seconds to wait.
        login_shell: If True, wraps command in bash -l to load .profile/.bashrc (for nvm etc).
    """
    cfg = pc()
    if login_shell:
        command = f"bash -l -c {_shell_quote(command)}"
    args = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        "-i", cfg["ssh_key"],
        f"{cfg['ssh_user']}@{cfg['ip']}",
        command,
    ]
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return -1, "", "SSH timeout"
    return proc.returncode, stdout.decode().strip(), stderr.decode().strip()


async def ssh_available() -> bool:
    """Check if SSH connection to PC works."""
    code, _, _ = await ssh_run("echo ok", timeout=10)
    return code == 0
