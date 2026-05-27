import logging

from django.db.models import Count
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from Jeeves.clients.models import Client
from Jeeves.concierge_platform.permissions import IsOwner
from .models import ToolCard, ToolConnection, InstalledMCPServer
from .mcp_discovery import (
    discover_or_parse, DiscoveryResult, PageParseResult, DiscoveryError,
    _discover_live, discover_stdio, install_npm_package, install_pip_package,
)
from .serializers_owner import (
    ToolCardOwnerSerializer,
    DiscoverRequestSerializer,
    FromUrlRequestSerializer,
    InstallPackageRequestSerializer,
)

logger = logging.getLogger(__name__)


def _detect_missing_env(error_text, run_command, run_args, package_name):
    """Try to figure out which env vars a server needs from its error output.

    Returns list of {"name": "VAR_NAME", "hint": "..."} or empty list.
    """
    import re
    import subprocess

    # 1. Check error text for common patterns
    env_patterns = re.findall(r'([A-Z][A-Z0-9_]{2,}(?:_KEY|_URL|_TOKEN|_SECRET|_ID)?)', error_text)
    known_prefixes = {'FIRECRAWL_', 'OPENAI_', 'ANTHROPIC_', 'COHERE_', 'GITHUB_', 'SLACK_',
                      'NOTION_', 'SUPABASE_', 'GOOGLE_', 'AWS_', 'AZURE_', 'STRIPE_',
                      'SENDGRID_', 'TWILIO_', 'BRAVE_', 'TAVILY_', 'SERPER_', 'PERPLEXITY_'}
    key_suffixes = ('_KEY', '_TOKEN', '_SECRET', '_URL', '_ID', '_API_KEY')

    found = []
    seen = set()
    for var in env_patterns:
        if var in seen:
            continue
        seen.add(var)
        is_known = any(var.startswith(p) for p in known_prefixes)
        is_key_like = var.endswith(key_suffixes)
        if is_known or is_key_like:
            found.append({'name': var, 'required': True})

    # 2. If nothing found in error, try running with --help or checking README patterns
    if not found and "must be provided" in error_text.lower():
        # Generic "must be provided" — try to extract from nearby text
        must_match = re.search(r'(?:Either\s+)?(\w+)(?:\s+or\s+(\w+))?\s+must be provided', error_text)
        if must_match:
            for g in must_match.groups():
                if g and g not in seen:
                    found.append({'name': g, 'required': True})
                    seen.add(g)

    return found


class ToolCardOwnerViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsOwner]
    serializer_class = ToolCardOwnerSerializer

    def get_queryset(self):
        return ToolCard.objects.annotate(
            connections_count=Count('connections'),
        ).order_by('sort_order', 'name')

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_builtin:
            return Response(
                {'error': 'Cannot delete built-in tools.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'])
    def discover(self, request):
        """Connect to MCP server URL or parse catalog page. Does not save."""
        ser = DiscoverRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        url = ser.validated_data['url']

        try:
            result = discover_or_parse(url)
        except DiscoveryError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if isinstance(result, DiscoveryResult):
            return Response({
                'type': 'live',
                'server_name': result.server_name,
                'tools': result.tools,
                'transport': result.transport,
            })

        # PageParseResult — info from catalog page
        return Response({
            'type': 'parsed',
            'server_name': result.server_name,
            'github_url': result.github_url,
            'npm_package': result.npm_package,
            'pip_package': result.pip_package,
            'sse_endpoint': result.sse_endpoint,
            'install_command': result.install_command,
            'mcp_config': result.mcp_config,
            'description': result.description,
            'transport_type': result.transport_type,
        })

    @action(detail=False, methods=['post'], url_path='from-url')
    def from_url(self, request):
        """Discover + create ToolCard + auto-connect to all clients."""
        ser = FromUrlRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        # 1. Discover — try live connection first
        try:
            result = discover_or_parse(data['url'])
        except DiscoveryError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # If we got a parsed page (not live endpoint), can't auto-connect
        if isinstance(result, PageParseResult):
            return Response(
                {'error': 'This is a catalog page. Use the discover endpoint first to see server info.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Create ToolCard
        transport = result.transport or 'sse'
        name = data['name'] or result.server_name or 'Unnamed MCP Server'
        tool_data = {
            'name': name,
            'tagline': f"External MCP server with {len(result.tools)} tools",
            'description': ', '.join(t['name'] for t in result.tools),
            'icon': data['icon'],
            'color': data['color'],
            'category': data['category'],
            'mcp_server_url': data['url'],
            'transport_type': transport,
            'is_builtin': False,
            'tools_schema': result.tools,
            'auth_type': 'none',
            'is_active': True,
            'is_system': True,
            'skill_scopes': {'scopes': data['targets']},
        }
        card_ser = ToolCardOwnerSerializer(data=tool_data)
        card_ser.is_valid(raise_exception=True)
        tool_card = card_ser.save()

        # 3. Auto-connect all clients
        now = timezone.now()
        clients = Client.objects.all()
        connections = []
        for client in clients:
            for target in data['targets']:
                connections.append(ToolConnection(
                    client=client,
                    tool_card=tool_card,
                    target=target,
                    status='connected',
                    enabled=True,
                    connected_at=now,
                ))
        ToolConnection.objects.bulk_create(connections, ignore_conflicts=True)

        # Re-fetch with annotation
        tool_card = self.get_queryset().get(pk=tool_card.pk)
        return Response(
            ToolCardOwnerSerializer(tool_card).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['post'], url_path='install')
    def install(self, request):
        """Install npm/pip MCP package, discover tools via stdio, create ToolCard, auto-connect."""
        ser = InstallPackageRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        package_name = data['package_name']
        package_type = data['package_type']

        # Check if already installed
        if InstalledMCPServer.objects.filter(package_name=package_name).exists():
            return Response(
                {'error': f'Package {package_name} is already installed.'},
                status=status.HTTP_409_CONFLICT,
            )

        # 1. Install the package
        try:
            if package_type == 'npm':
                version = install_npm_package(package_name)
            else:
                version = install_pip_package(package_name)
        except DiscoveryError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Determine run command
        run_command = data['run_command']
        run_args = data['run_args']
        if not run_command:
            if package_type == 'npm':
                # npx <package>
                run_command = 'npx'
                run_args = ['-y', package_name] + run_args
            else:
                # python -m <package> or just <package>
                run_command = package_name.replace('-', '_')

        # 3. Discover tools via stdio
        import os
        env = {**os.environ, **(data['env_config'] or {})} if data['env_config'] else None
        try:
            result = discover_stdio(run_command, run_args, env)
        except DiscoveryError as e:
            err_text = str(e)
            # Detect missing env var errors — common patterns from MCP servers
            env_hints = _detect_missing_env(err_text, run_command, run_args, package_name)
            if env_hints:
                return Response({
                    'error': 'needs_env',
                    'message': f'Package installed. Server requires configuration:',
                    'env_vars': env_hints,
                    'package_name': package_name,
                    'package_type': package_type,
                    'version': version,
                    'run_command': run_command,
                    'run_args': run_args,
                }, status=status.HTTP_400_BAD_REQUEST)
            return Response(
                {'error': f'Package installed but tool discovery failed: {e}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 4. Create ToolCard
        name = data['name'] or result.server_name or package_name
        tool_data = {
            'name': name,
            'tagline': f"Local MCP server with {len(result.tools)} tools",
            'description': ', '.join(t['name'] for t in result.tools),
            'icon': data['icon'],
            'color': data['color'],
            'category': data['category'],
            'transport_type': 'stdio',
            'is_builtin': False,
            'tools_schema': result.tools,
            'auth_type': 'none',
            'is_active': True,
            'is_system': True,
            'skill_scopes': {'scopes': data['targets']},
        }
        card_ser = ToolCardOwnerSerializer(data=tool_data)
        card_ser.is_valid(raise_exception=True)
        tool_card = card_ser.save()

        # 5. Create InstalledMCPServer record
        InstalledMCPServer.objects.create(
            tool_card=tool_card,
            package_name=package_name,
            package_type=package_type,
            version=version,
            run_command=run_command,
            run_args=run_args,
            env_config=data['env_config'],
            source_url=data['source_url'],
            status='installed',
        )

        # 6. Auto-connect all clients
        now = timezone.now()
        clients = Client.objects.all()
        connections = []
        for client in clients:
            for target in data['targets']:
                connections.append(ToolConnection(
                    client=client,
                    tool_card=tool_card,
                    target=target,
                    status='connected',
                    enabled=True,
                    connected_at=now,
                ))
        ToolConnection.objects.bulk_create(connections, ignore_conflicts=True)

        tool_card = self.get_queryset().get(pk=tool_card.pk)
        return Response(
            ToolCardOwnerSerializer(tool_card).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def refresh(self, request, pk=None):
        """Re-discover tools from existing MCP server URL."""
        tool_card = self.get_object()
        if not tool_card.mcp_server_url:
            return Response(
                {'error': 'No MCP server URL configured.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = _discover_live(tool_card.mcp_server_url)
        except DiscoveryError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tool_card.tools_schema = result.tools
        tool_card.save(update_fields=['tools_schema', 'updated_at'])

        tool_card = self.get_queryset().get(pk=tool_card.pk)
        return Response(ToolCardOwnerSerializer(tool_card).data)
