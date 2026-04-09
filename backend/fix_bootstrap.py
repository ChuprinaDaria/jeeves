api_key_obj, _ = ClientAPIKey.objects.get_or_create(
    key=client_token,
    defaults={
        'client': client,
        'name': f'bootstrap:{client_token}',
        'is_active': True
    }
)
