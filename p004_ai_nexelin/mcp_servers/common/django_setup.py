"""Bootstrap Django ORM for standalone MCP server processes."""
import os
import django


def setup():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MASTER.settings')
    django.setup()
