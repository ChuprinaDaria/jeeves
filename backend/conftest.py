"""
Root pytest conftest for the Jeeves backend.

Loaded automatically by pytest from the `backend/` directory (which is /app
inside the `web` container). Two responsibilities:

1.  Make sure the backend root is on sys.path so imports like
    `from Jeeves.concierge_platform.models import ...` work regardless of
    which CWD pytest is invoked from. The pyproject.toml pytest config sets
    `django_find_project = false`, which disables Django's auto-path logic,
    so we add it explicitly here.

2.  Provide a stable test encryption key for EncryptedJSONField so the
    fernet-backed fields can be round-tripped in tests.

The pgvector extension is created by EmbeddingModel's initial migration,
which runs before any other migration that uses VectorField — no pytest
hook needed.
"""
import os
import sys

# --- 1) sys.path fix ---------------------------------------------------------
_BACKEND_ROOT = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

import pytest


# --- 2) EncryptedJSONField test key ------------------------------------------
@pytest.fixture(autouse=True, scope='session')
def _use_test_encryption_key():
    """Use a stable test key for EncryptedJSONField — same key for whole test session."""
    from cryptography.fernet import Fernet
    from django.conf import settings
    settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
