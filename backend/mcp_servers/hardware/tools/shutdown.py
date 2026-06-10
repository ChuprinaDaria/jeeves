from mcp_servers.hardware.utils.config import pc
from mcp_servers.hardware.utils.network import ping
from mcp_servers.hardware.utils.ssh import ssh_run


async def pc_shutdown() -> str:
    """Вимикає ПК через SSH."""
    cfg = pc()

    if not await ping(cfg["ip"]):
        return "ПК вже вимкнений."

    code, _, stderr = await ssh_run("sudo shutdown -h now", timeout=10)
    if code in (0, -1):
        # -1 = connection closed by shutdown, which is expected
        return "ПК вимикається."
    return f"Помилка при вимкненні: {stderr}"
