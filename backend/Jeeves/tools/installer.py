import asyncio
import logging
import os
import subprocess

from .resolvers import ResolvedPackage

logger = logging.getLogger(__name__)

DISCOVERY_TIMEOUT = 15


class InstallError(Exception):
    pass


def install_package(pkg: ResolvedPackage) -> None:
    if pkg.package_type == 'npm':
        cmd = ['npm', 'install', '-g', pkg.package_name]
    elif pkg.package_type == 'pypi':
        cmd = ['pip', 'install', pkg.package_name]
    else:
        raise InstallError(f'Unsupported package type: {pkg.package_type}')

    logger.info('Installing %s package: %s', pkg.package_type, pkg.package_name)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        error_msg = result.stderr.strip() or result.stdout.strip() or 'Unknown error'
        raise InstallError(error_msg)

    logger.info('Successfully installed %s', pkg.package_name)


def uninstall_package(package_name: str, package_type: str) -> None:
    if package_type == 'npm':
        cmd = ['npm', 'uninstall', '-g', package_name]
    elif package_type == 'pypi':
        cmd = ['pip', 'uninstall', '-y', package_name]
    else:
        return

    logger.info('Uninstalling %s package: %s', package_type, package_name)
    subprocess.run(cmd, capture_output=True, text=True, timeout=60)


async def _discover_stdio(
    run_command: str,
    run_args: list,
    env_config: dict | None = None,
) -> list[dict]:
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters

    env = {**os.environ}
    for key in ('SECRET_KEY', 'DATABASE_URL'):
        env.pop(key, None)
    if env_config:
        env.update(env_config)

    params = StdioServerParameters(
        command=run_command,
        args=run_args,
        env=env,
    )

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.list_tools()
            return [
                {
                    'name': t.name,
                    'description': t.description or '',
                    'inputSchema': t.inputSchema if hasattr(t, 'inputSchema') else {},
                }
                for t in result.tools
            ]


def discover_stdio_tools(
    run_command: str,
    run_args: list,
    env_config: dict | None = None,
) -> list[dict]:
    try:
        tools = asyncio.run(
            asyncio.wait_for(
                _discover_stdio(run_command, run_args, env_config),
                timeout=DISCOVERY_TIMEOUT,
            )
        )
        if not tools:
            raise InstallError('Server returned zero tools.')
        return tools
    except InstallError:
        raise
    except asyncio.TimeoutError:
        raise InstallError(f'Server did not respond within {DISCOVERY_TIMEOUT}s.')
    except Exception as e:
        raise InstallError(f'Failed to discover tools: {e}')
