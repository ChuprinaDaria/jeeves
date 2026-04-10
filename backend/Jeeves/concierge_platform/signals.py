from django.core.cache import cache


def _clear_flag_cache(flag_key):
    """Clear cache for a specific flag. Iterates known client PKs.
    For large deployments, switch to django-redis with delete_pattern()."""
    from Jeeves.clients.models import Client
    for client_pk in Client.objects.values_list('pk', flat=True).iterator():
        cache.delete(f'ff:{flag_key}:{client_pk}')
    cache.delete(f'ff:{flag_key}:global')


def on_feature_flag_save(sender, instance, **kwargs):
    _clear_flag_cache(instance.key)


def on_feature_flag_m2m_change(sender, instance, **kwargs):
    _clear_flag_cache(instance.key)
