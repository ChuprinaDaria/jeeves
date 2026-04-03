"""
MCP builtin tools for Nexy to manage bridge connections and canvas nodes.

Tools:
- bridge_start_connection: Initiate bridge auth (QR or cookies)
- bridge_check_status: Check bridge connection status
- canvas_add_tool_connection: Create ToolConnection + canvas node
- canvas_remove_tool_connection: Remove ToolConnection
- canvas_list_connections: List all bridge connections
"""

import logging

from asgiref.sync import sync_to_async
from django.utils import timezone

from MASTER.clients.services.bridge_service import bridge_service, BridgeServiceError

logger = logging.getLogger(__name__)


async def bridge_tools(connection, tool_name, **kwargs):
    """Dispatcher for bridge-related MCP tools."""
    client = connection.client

    handlers = {
        'bridge_start_connection': _bridge_start_connection,
        'bridge_check_status': _bridge_check_status,
        'canvas_add_tool_connection': _canvas_add_tool_connection,
        'canvas_remove_tool_connection': _canvas_remove_tool_connection,
        'canvas_list_connections': _canvas_list_connections,
    }

    handler = handlers.get(tool_name)
    if not handler:
        return {'error': f'Unknown tool: {tool_name}'}

    try:
        return await handler(client, **kwargs)
    except BridgeServiceError as e:
        return {'error': str(e)}
    except Exception as e:
        logger.error(f'Bridge tool {tool_name} error: {e}', exc_info=True)
        return {'error': f'Internal error: {str(e)}'}


async def _bridge_start_connection(client, bridge_type=None, **kwargs):
    if not bridge_type:
        return {'error': 'bridge_type is required'}

    result = await bridge_service.start_login(client, bridge_type)

    if result['auth_flow'] == 'cookies':
        return {
            'type': 'auth_popup',
            'auth_flow': 'cookies',
            'popup_url': result.get('popup_url', ''),
            'bridge_type': bridge_type,
            'cookie_domains': result.get('cookie_domains', []),
            'required_cookies': result.get('required_cookies', []),
            'process_id': result.get('process_id', ''),
            'step_id': result.get('step_id', ''),
        }
    elif result['auth_flow'] == 'qr_code':
        return {
            'type': 'qr_code',
            'qr': result.get('qr', ''),
            'bridge_type': bridge_type,
            'process_id': result.get('process_id', ''),
        }
    else:
        return result


async def _bridge_check_status(client, bridge_type=None, **kwargs):
    if not bridge_type:
        connections = await bridge_service.list_connections(client)
        return {'type': 'status_card', 'connections': connections}

    result = await bridge_service.check_status(client, bridge_type)
    return {
        'type': 'status_card',
        'bridge_type': bridge_type,
        'status': result.get('status', 'disconnected'),
        'remote_id': result.get('remote_id'),
        'connected_at': result.get('connected_at'),
        'error': result.get('error', ''),
    }


async def _canvas_add_tool_connection(client, bridge_type=None, targets=None, **kwargs):
    if not bridge_type:
        return {'error': 'bridge_type is required'}

    from MASTER.tools.models import ToolCard, ToolConnection
    from MASTER.clients.models_bridge import BridgeConfig

    try:
        tool_card = await sync_to_async(ToolCard.objects.get)(slug=bridge_type)
    except ToolCard.DoesNotExist:
        return {'error': f'ToolCard not found for {bridge_type}'}

    if not targets:
        try:
            config = await sync_to_async(BridgeConfig.objects.get)(bridge_type=bridge_type)
            targets = config.default_scopes
        except BridgeConfig.DoesNotExist:
            targets = ['assistant']

    nodes_created = []
    for target in targets:
        conn, created = await sync_to_async(ToolConnection.objects.update_or_create)(
            client=client,
            tool_card=tool_card,
            target=target,
            defaults={
                'status': 'connected',
                'enabled': True,
                'connected_at': timezone.now(),
                'last_error': '',
                'error_count': 0,
            },
        )
        nodes_created.append(f'{target}-{bridge_type}')

    return {
        'type': 'connection_created',
        'bridge_type': bridge_type,
        'targets': targets,
        'nodes_created': nodes_created,
    }


async def _canvas_remove_tool_connection(client, connection_id=None, bridge_type=None, **kwargs):
    from MASTER.tools.models import ToolConnection

    if connection_id:
        try:
            conn = await sync_to_async(ToolConnection.objects.get)(pk=connection_id, client=client)
            await sync_to_async(conn.delete)()
            return {'type': 'connection_removed', 'connection_id': connection_id}
        except ToolConnection.DoesNotExist:
            return {'error': f'Connection {connection_id} not found'}

    if bridge_type:
        from MASTER.tools.models import ToolCard
        try:
            tool_card = await sync_to_async(ToolCard.objects.get)(slug=bridge_type)
        except ToolCard.DoesNotExist:
            return {'error': f'ToolCard not found for {bridge_type}'}

        deleted, _ = await sync_to_async(
            ToolConnection.objects.filter(client=client, tool_card=tool_card).delete
        )()
        return {'type': 'connection_removed', 'bridge_type': bridge_type, 'deleted_count': deleted}

    return {'error': 'connection_id or bridge_type required'}


async def _canvas_list_connections(client, **kwargs):
    from MASTER.tools.models import ToolConnection

    connections = await sync_to_async(list)(
        ToolConnection.objects.filter(client=client)
        .select_related('tool_card')
        .values(
            'id', 'tool_card__slug', 'tool_card__name', 'status',
            'target', 'connected_at', 'enabled'
        )
    )

    bridge_connections = await bridge_service.list_connections(client)

    return {
        'canvas_connections': connections,
        'bridge_connections': bridge_connections,
    }
