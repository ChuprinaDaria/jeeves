import pytest
from MASTER.concierge_platform.models import PlatformDefaults


@pytest.mark.django_db
class TestPlatformDefaults:
    def test_singleton_get_creates_if_missing(self):
        assert PlatformDefaults.objects.count() == 0
        defaults = PlatformDefaults.get()
        assert defaults.pk == 1
        assert PlatformDefaults.objects.count() == 1

    def test_singleton_get_returns_existing(self):
        PlatformDefaults.objects.create(pk=1)
        defaults = PlatformDefaults.get()
        assert defaults.pk == 1
        assert PlatformDefaults.objects.count() == 1

    def test_save_always_pk_1(self):
        d = PlatformDefaults()
        d.save()
        assert d.pk == 1
        d2 = PlatformDefaults()
        d2.save()
        assert d2.pk == 1
        assert PlatformDefaults.objects.count() == 1
