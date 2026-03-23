from django.db import migrations


def seed_sales_intel(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    ToolCard.objects.get_or_create(
        slug='sales-intel',
        defaults={
            'name': 'Sales Intelligence',
            'tagline': 'Дослідження компаній: techstack, сайт, дані',
            'tagline_i18n': {
                'en': 'Company research: techstack, website data, company intel',
                'de': 'Unternehmensrecherche: Techstack, Website-Daten',
            },
            'description': 'Detect company tech stacks and extract structured data from websites.',
            'icon': 'search',
            'category': 'crm',
            'color': '#3b82f6',
            'transport_type': 'builtin',
            'is_builtin': True,
            'builtin_handler': 'mcp_hub.builtin.sales_intel',
            'auth_type': 'none',
            'skill_scopes': {
                'scopes': ['assistant'],
                'bidirectional': False,
            },
        },
    )


def unseed(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    ToolCard.objects.filter(slug='sales-intel').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('tools', '0010_seed_leads_tool'),
    ]

    operations = [
        migrations.RunPython(seed_sales_intel, unseed),
    ]
