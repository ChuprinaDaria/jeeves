from django.apps import AppConfig


class ClientsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Jeeves.clients'
    
    def ready(self):
        import Jeeves.clients.signals
        import Jeeves.rag.qdrant_sync  # noqa: F401 — registers post_save/post_delete signals
        import Jeeves.clients.models_bridge  # noqa: F401 — register bridge models