import pytest


@pytest.fixture(autouse=True, scope='session')
def _use_test_encryption_key():
    """Use a stable test key for EncryptedJSONField — same key for whole test session."""
    from cryptography.fernet import Fernet
    from django.conf import settings
    settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
