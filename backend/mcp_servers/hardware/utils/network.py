import asyncio


async def ping(ip: str, timeout: int = 2) -> bool:
    """Ping host, return True if reachable."""
    proc = await asyncio.create_subprocess_exec(
        "ping", "-c", "1", "-W", str(timeout), ip,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    code = await proc.wait()
    return code == 0


async def send_wol(mac: str, broadcast: str = "255.255.255.255") -> None:
    """Send Wake-on-LAN magic packet via wakeonlan CLI."""
    proc = await asyncio.create_subprocess_exec(
        "wakeonlan", "-i", broadcast, mac,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.wait()


async def wait_online(ip: str, timeout: int = 120, interval: int = 3) -> bool:
    """Ping IP every `interval` seconds until it responds or timeout."""
    elapsed = 0
    while elapsed < timeout:
        if await ping(ip):
            return True
        await asyncio.sleep(interval)
        elapsed += interval
    return False
