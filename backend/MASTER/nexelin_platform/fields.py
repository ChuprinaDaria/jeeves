from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models
import json


class EncryptedJSONField(models.TextField):
    """Stores JSON data encrypted at rest with Fernet symmetric encryption."""

    def get_prep_value(self, value):
        if value is None:
            return None
        f = Fernet(settings.FIELD_ENCRYPTION_KEY.encode()
                   if isinstance(settings.FIELD_ENCRYPTION_KEY, str)
                   else settings.FIELD_ENCRYPTION_KEY)
        return f.encrypt(json.dumps(value).encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None:
            return {}
        f = Fernet(settings.FIELD_ENCRYPTION_KEY.encode()
                   if isinstance(settings.FIELD_ENCRYPTION_KEY, str)
                   else settings.FIELD_ENCRYPTION_KEY)
        return json.loads(f.decrypt(value.encode()).decode())

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        return name, path, args, kwargs


class EncryptedTextField(models.TextField):
    """Stores text data encrypted at rest with Fernet symmetric encryption."""

    def get_prep_value(self, value):
        if not value:
            return value
        f = Fernet(settings.FIELD_ENCRYPTION_KEY.encode()
                   if isinstance(settings.FIELD_ENCRYPTION_KEY, str)
                   else settings.FIELD_ENCRYPTION_KEY)
        return f.encrypt(value.encode()).decode()

    def from_db_value(self, value, expression, connection):
        if not value:
            return ''
        f = Fernet(settings.FIELD_ENCRYPTION_KEY.encode()
                   if isinstance(settings.FIELD_ENCRYPTION_KEY, str)
                   else settings.FIELD_ENCRYPTION_KEY)
        return f.decrypt(value.encode()).decode()

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        return name, path, args, kwargs
