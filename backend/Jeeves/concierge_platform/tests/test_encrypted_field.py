import pytest
from Jeeves.concierge_platform.fields import EncryptedJSONField
from Jeeves.concierge_platform.fields import EncryptedTextField


@pytest.mark.django_db
class TestEncryptedJSONField:
    def test_round_trip(self):
        field = EncryptedJSONField()
        original = {'token': 'secret_abc123', 'nested': {'key': 'value'}}
        encrypted = field.get_prep_value(original)
        assert isinstance(encrypted, str)
        assert 'secret_abc123' not in encrypted
        decrypted = field.from_db_value(encrypted, None, None)
        assert decrypted == original

    def test_none_handling(self):
        field = EncryptedJSONField()
        assert field.get_prep_value(None) is None
        assert field.from_db_value(None, None, None) == {}

    def test_empty_dict(self):
        field = EncryptedJSONField()
        encrypted = field.get_prep_value({})
        decrypted = field.from_db_value(encrypted, None, None)
        assert decrypted == {}


@pytest.mark.django_db
class TestEncryptedTextField:
    def test_round_trip(self):
        field = EncryptedTextField()
        original = 'sk-proj-abc123def456ghi789'
        encrypted = field.get_prep_value(original)
        assert isinstance(encrypted, str)
        assert 'sk-proj' not in encrypted
        decrypted = field.from_db_value(encrypted, None, None)
        assert decrypted == original

    def test_none_stays_none(self):
        field = EncryptedTextField()
        assert field.get_prep_value(None) is None
        assert field.from_db_value(None, None, None) == ''

    def test_empty_string_passthrough(self):
        field = EncryptedTextField()
        # Empty strings bypass encryption per current EncryptedTextField logic
        assert field.get_prep_value('') == ''
        assert field.from_db_value('', None, None) == ''
