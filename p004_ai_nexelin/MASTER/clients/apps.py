from django.apps import AppConfig


class ClientsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'MASTER.clients'
    
    def ready(self):
        import MASTER.clients.signals
        import MASTER.rag.qdrant_sync  # noqa: F401 — registers post_save/post_delete signals