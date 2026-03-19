from django.apps import AppConfig


class PlatformConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'MASTER.nexelin_platform'
    verbose_name = 'Platform'

    def ready(self):
        from . import signals
        from .models import FeatureFlag
        from django.db.models.signals import post_save, m2m_changed
        post_save.connect(signals.on_feature_flag_save, sender=FeatureFlag)
        m2m_changed.connect(signals.on_feature_flag_m2m_change,
                            sender=FeatureFlag.enabled_clients.through)
