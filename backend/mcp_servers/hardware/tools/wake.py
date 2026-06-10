import asyncio

from mcp_servers.hardware.utils.config import pc, timeouts
from mcp_servers.hardware.utils.network import send_wol, wait_online, ping
from mcp_servers.hardware.utils.ssh import ssh_available


async def pc_wake() -> str:
    """Включає ПК через Wake-on-LAN і чекає поки він завантажиться."""
    cfg = pc()
    t = timeouts()

    if await ping(cfg["ip"]):
        if await ssh_available():
            return "ПК вже увімкнений і доступний по SSH."
        return "ПК онлайн, але SSH ще недоступний. Зачекай хвилину."

    await send_wol(cfg["mac"], cfg.get("broadcast", "255.255.255.255"))

    online = await wait_online(cfg["ip"], timeout=t["wol_wait"], interval=t["ping_interval"])
    if not online:
        return "ПК не відповідає протягом 120 секунд. Перевір BIOS/мережу."

    # Чекаємо поки SSH піднімається
    await asyncio.sleep(t["ssh_wait"])

    if await ssh_available():
        return "ПК увімкнений і доступний по SSH."
    return "ПК увімкнений (відповідає на ping), але SSH ще не піднявся. Спробуй через хвилину."
