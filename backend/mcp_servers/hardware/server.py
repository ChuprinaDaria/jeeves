"""MCP Hardware server — remote PC control (Wake-on-LAN, SSH, filesystem, tmux workspaces).

Port of sloth/pi-remote. Reads config from ``HARDWARE_CONFIG_PATH`` env var or
the legacy ``PI_REMOTE_CONFIG`` (default: ``mcp_servers/hardware/config.yaml``).
"""
from fastmcp import FastMCP

from mcp_servers.hardware.tools.wake import pc_wake as _pc_wake
from mcp_servers.hardware.tools.shutdown import pc_shutdown as _pc_shutdown
from mcp_servers.hardware.tools.status import pc_status as _pc_status
from mcp_servers.hardware.tools.workspace import (
    pc_launch_workspace as _pc_launch_workspace,
    pc_stop_workspace as _pc_stop_workspace,
)
from mcp_servers.hardware.tools.filesystem import (
    pc_list_dir as _pc_list_dir,
    pc_read_file as _pc_read_file,
    pc_write_file as _pc_write_file,
    pc_find_files as _pc_find_files,
    pc_grep as _pc_grep,
)
from mcp_servers.hardware.tools.system import (
    pc_disk_usage as _pc_disk_usage,
    pc_processes as _pc_processes,
    pc_screenshot as _pc_screenshot,
    pc_clipboard_read as _pc_clipboard_read,
    pc_clipboard_write as _pc_clipboard_write,
    pc_open_url as _pc_open_url,
    pc_system_info as _pc_system_info,
    pc_run_safe as _pc_run_safe,
)

mcp = FastMCP(
    "mcp-hardware",
    description="Concierge hardware server. Remote-control a workstation via SSH/Wake-on-LAN.",
)


@mcp.tool()
async def pc_wake() -> str:
    """Wake the workstation via Wake-on-LAN and wait until SSH is reachable."""
    return await _pc_wake()


@mcp.tool()
async def pc_shutdown() -> str:
    """Shut down the workstation over SSH."""
    return await _pc_shutdown()


@mcp.tool()
async def pc_status() -> str:
    """Report workstation state: online/offline, SSH, uptime, active tmux sessions, VS Code."""
    return await _pc_status()


@mcp.tool()
async def pc_launch_workspace(repo: str) -> str:
    """Start a remote-control workspace for a git repo in tmux.

    Args:
        repo: project name (auto-detected from git repos on the workstation).
    """
    return await _pc_launch_workspace(repo)


@mcp.tool()
async def pc_stop_workspace(repo: str = "") -> str:
    """Stop a workspace tmux session. Empty repo stops all workspaces.

    Args:
        repo: project name; empty = stop all.
    """
    return await _pc_stop_workspace(repo or None)


@mcp.tool()
async def pc_list_dir(path: str = "~") -> str:
    """List directory contents on the workstation.

    Args:
        path: directory path (default: home ~).
    """
    return await _pc_list_dir(path)


@mcp.tool()
async def pc_read_file(path: str, offset: int = 0, limit: int = 200) -> str:
    """Read file contents on the workstation.

    Args:
        path: file path.
        offset: start at line N (0 = beginning).
        limit: number of lines (max 500).
    """
    return await _pc_read_file(path, offset, limit)


@mcp.tool()
async def pc_write_file(path: str, content: str) -> str:
    """Write content to a file on the workstation. Creates if missing. Does not delete.

    Args:
        path: file path.
        content: text to write.
    """
    return await _pc_write_file(path, content)


@mcp.tool()
async def pc_find_files(pattern: str, path: str = "~", max_depth: int = 3) -> str:
    """Find files by glob pattern on the workstation.

    Args:
        pattern: glob (e.g. ``*.py``, ``docker-compose*``).
        path: search root (default: ~).
        max_depth: depth (default: 3, max: 5).
    """
    return await _pc_find_files(pattern, path, max_depth)


@mcp.tool()
async def pc_grep(pattern: str, path: str, glob_filter: str = "") -> str:
    """Grep text in files on the workstation.

    Args:
        pattern: text or regex.
        path: file or directory.
        glob_filter: file filter (e.g. ``*.py``).
    """
    return await _pc_grep(pattern, path, glob_filter)


@mcp.tool()
async def pc_disk_usage() -> str:
    """Show disk usage: totals + top directories by size."""
    return await _pc_disk_usage()


@mcp.tool()
async def pc_processes(sort_by: str = "cpu") -> str:
    """Show top processes by CPU or RAM.

    Args:
        sort_by: ``cpu`` or ``mem``.
    """
    return await _pc_processes(sort_by)


@mcp.tool()
async def pc_screenshot() -> str:
    """Capture the workstation screen, save to ``/tmp/screenshot.png``."""
    return await _pc_screenshot()


@mcp.tool()
async def pc_clipboard_read() -> str:
    """Read the workstation clipboard."""
    return await _pc_clipboard_read()


@mcp.tool()
async def pc_clipboard_write(text: str) -> str:
    """Write text to the workstation clipboard.

    Args:
        text: text to copy.
    """
    return await _pc_clipboard_write(text)


@mcp.tool()
async def pc_open_url(url: str) -> str:
    """Open a URL in the workstation browser.

    Args:
        url: URL to open (e.g. ``google.com`` or ``https://github.com``).
    """
    return await _pc_open_url(url)


@mcp.tool()
async def pc_system_info() -> str:
    """Full system info: CPU, RAM, temperature, GPU, network, uptime."""
    return await _pc_system_info()


@mcp.tool()
async def pc_run_safe(command: str) -> str:
    """Run a whitelisted command on the workstation (git, docker, npm, python, ls, curl…).

    Args:
        command: command to run.
    """
    return await _pc_run_safe(command)


if __name__ == "__main__":
    mcp.run(transport="stdio")
