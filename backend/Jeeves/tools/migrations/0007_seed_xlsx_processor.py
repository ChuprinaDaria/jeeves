from django.db import migrations


def forward(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    ToolCard.objects.get_or_create(
        slug='xlsx-processor',
        defaults={
            'name': 'XLSX Processor',
            'tagline': 'Створення, редагування та аналіз Excel-файлів',
            'tagline_i18n': {
                'en': 'Create, edit, and analyze Excel spreadsheets',
                'de': 'Excel-Tabellen erstellen, bearbeiten und analysieren',
            },
            'description': '',
            'icon': 'file-spreadsheet',
            'category': 'ai',
            'color': '#217346',
            'transport_type': 'builtin',
            'is_builtin': True,
            'builtin_handler': 'mcp_hub.builtin.xlsx_processor',
            'auth_type': 'none',
            'skill_scopes': {'scopes': ['assistant', 'manager'], 'bidirectional': True},
        })


def reverse(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    ToolCard.objects.filter(slug='xlsx-processor').delete()


class Migration(migrations.Migration):
    dependencies = [('tools', '0006_edgemiddleware_toolcard_skill_scopes')]
    operations = [migrations.RunPython(forward, reverse)]
