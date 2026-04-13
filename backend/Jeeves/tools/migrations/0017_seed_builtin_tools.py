from django.db import migrations


BUILTIN_TOOLS = [
    {
        'name': 'RAG Knowledge Search',
        'slug': 'rag',
        'tagline': 'Search knowledge base with semantic retrieval',
        'description': 'RAG pipeline — vector search, context building, reranking.',
        'icon': 'search',
        'color': '#3b82f6',
        'category': 'ai',
        'transport_type': 'builtin',
        'builtin_handler': 'mcp_servers.rag.server',
        'is_builtin': True,
        'is_system': True,
        'is_active': True,
        'auth_type': 'none',
        'sort_order': 10,
        'skill_scopes': {'scopes': ['assistant', 'manager']},
    },
    {
        'name': 'Escalation',
        'slug': 'escalation',
        'tagline': 'Escalate conversations to human managers',
        'description': 'HITL manager escalation with availability checks.',
        'icon': 'arrow-up-right',
        'color': '#ef4444',
        'category': 'communication',
        'transport_type': 'builtin',
        'builtin_handler': 'mcp_servers.escalation.server',
        'is_builtin': True,
        'is_system': True,
        'is_active': True,
        'auth_type': 'none',
        'sort_order': 20,
        'skill_scopes': {'scopes': ['assistant']},
    },
    {
        'name': 'Lead Management',
        'slug': 'leads',
        'tagline': 'Capture and score leads from conversations',
        'description': 'Save leads with contact info, scoring, and session tracking.',
        'icon': 'user-plus',
        'color': '#10b981',
        'category': 'crm',
        'transport_type': 'builtin',
        'builtin_handler': 'mcp_servers.leads.server',
        'is_builtin': True,
        'is_system': True,
        'is_active': True,
        'auth_type': 'none',
        'sort_order': 30,
        'skill_scopes': {'scopes': ['assistant']},
    },
    {
        'name': 'Email',
        'slug': 'email',
        'tagline': 'Send emails from conversations',
        'description': 'Email integration for agent-driven communications.',
        'icon': 'mail',
        'color': '#8b5cf6',
        'category': 'communication',
        'transport_type': 'builtin',
        'builtin_handler': 'mcp_servers.email.server',
        'is_builtin': True,
        'is_system': True,
        'is_active': True,
        'auth_type': 'none',
        'sort_order': 40,
        'skill_scopes': {'scopes': ['assistant', 'manager']},
    },
    {
        'name': 'Memory',
        'slug': 'memory',
        'tagline': 'Conversation memory and context persistence',
        'description': 'Store and retrieve conversation memory across sessions.',
        'icon': 'brain',
        'color': '#f59e0b',
        'category': 'ai',
        'transport_type': 'builtin',
        'builtin_handler': 'mcp_servers.memory.server',
        'is_builtin': True,
        'is_system': True,
        'is_active': True,
        'auth_type': 'none',
        'sort_order': 50,
        'skill_scopes': {'scopes': ['assistant']},
    },
    {
        'name': 'Coaching',
        'slug': 'coaching',
        'tagline': 'AI coaching for conversation improvement',
        'description': 'Review conversations, find gaps, suggest knowledge base updates.',
        'icon': 'graduation-cap',
        'color': '#06b6d4',
        'category': 'ai',
        'transport_type': 'builtin',
        'builtin_handler': 'mcp_servers.coaching.server',
        'is_builtin': True,
        'is_system': False,
        'is_active': True,
        'auth_type': 'none',
        'sort_order': 60,
        'skill_scopes': {'scopes': ['manager']},
    },
    {
        'name': 'Sales Intelligence',
        'slug': 'sales-intel',
        'tagline': 'Sales insights and analytics',
        'description': 'Sales intelligence tools for conversation analysis.',
        'icon': 'chart-bar',
        'color': '#ec4899',
        'category': 'analytics',
        'transport_type': 'builtin',
        'builtin_handler': 'mcp_servers.sales_intel.server',
        'is_builtin': True,
        'is_system': False,
        'is_active': True,
        'auth_type': 'none',
        'sort_order': 70,
        'skill_scopes': {'scopes': ['manager']},
    },
    {
        'name': 'XLSX Export',
        'slug': 'xlsx',
        'tagline': 'Generate Excel spreadsheets',
        'description': 'Create and export XLSX spreadsheets from conversation data.',
        'icon': 'table',
        'color': '#22c55e',
        'category': 'productivity',
        'transport_type': 'builtin',
        'builtin_handler': 'mcp_servers.xlsx.server',
        'is_builtin': True,
        'is_system': False,
        'is_active': True,
        'auth_type': 'none',
        'sort_order': 80,
        'skill_scopes': {'scopes': ['assistant', 'manager']},
    },
]


def seed_tools(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    for tool_data in BUILTIN_TOOLS:
        ToolCard.objects.update_or_create(
            slug=tool_data['slug'],
            defaults=tool_data,
        )


def unseed_tools(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    slugs = [t['slug'] for t in BUILTIN_TOOLS]
    ToolCard.objects.filter(slug__in=slugs, is_builtin=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tools', '0016_seed_meta_linkedin_tools'),
    ]

    operations = [
        migrations.RunPython(seed_tools, unseed_tools),
    ]
