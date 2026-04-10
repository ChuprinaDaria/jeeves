from datetime import timedelta

import pytest
from django.utils import timezone

from Jeeves.concierge_platform.models import PlatformLicense


@pytest.mark.django_db
class TestPlatformLicense:
    def test_singleton_get_creates_if_missing(self):
        assert PlatformLicense.objects.count() == 0
        lic = PlatformLicense.get()
        assert lic.pk == 1
        assert PlatformLicense.objects.count() == 1
        assert lic.status == PlatformLicense.LicenseStatus.MISSING

    def test_singleton_save_always_pk_1(self):
        a = PlatformLicense()
        a.save()
        b = PlatformLicense()
        b.save()
        assert a.pk == 1
        assert b.pk == 1
        assert PlatformLicense.objects.count() == 1

    def test_is_setup_complete_false_by_default(self):
        lic = PlatformLicense.get()
        assert lic.is_setup_complete is False

    def test_is_setup_complete_true_when_set(self):
        lic = PlatformLicense.get()
        lic.setup_completed_at = timezone.now()
        lic.save()
        assert lic.is_setup_complete is True

    def test_grace_period_days_is_7(self):
        assert PlatformLicense.get().grace_period_days == 7

    def test_is_in_grace_period_false_when_valid(self):
        lic = PlatformLicense.get()
        lic.status = PlatformLicense.LicenseStatus.VALID
        lic.last_verified_at = timezone.now()
        lic.save()
        assert lic.is_in_grace_period is False

    def test_is_in_grace_period_true_within_window_using_last_verified(self):
        lic = PlatformLicense.get()
        lic.status = PlatformLicense.LicenseStatus.GRACE
        lic.last_verified_at = timezone.now() - timedelta(days=3)
        lic.save()
        assert lic.is_in_grace_period is True

    def test_is_in_grace_period_false_after_7_days(self):
        lic = PlatformLicense.get()
        lic.status = PlatformLicense.LicenseStatus.GRACE
        lic.last_verified_at = timezone.now() - timedelta(days=8)
        lic.save()
        assert lic.is_in_grace_period is False

    def test_is_in_grace_period_uses_last_attempt_when_last_verified_missing(self):
        lic = PlatformLicense.get()
        lic.status = PlatformLicense.LicenseStatus.GRACE
        lic.last_verified_at = None
        lic.last_attempt_at = timezone.now() - timedelta(days=2)
        lic.save()
        assert lic.is_in_grace_period is True

    def test_is_in_grace_period_false_when_no_anchors(self):
        lic = PlatformLicense.get()
        lic.status = PlatformLicense.LicenseStatus.GRACE
        lic.last_verified_at = None
        lic.last_attempt_at = None
        lic.save()
        assert lic.is_in_grace_period is False

    def test_grace_days_remaining_null_when_not_grace(self):
        lic = PlatformLicense.get()
        lic.status = PlatformLicense.LicenseStatus.VALID
        lic.save()
        assert lic.grace_days_remaining is None

    def test_grace_days_remaining_counts_down(self):
        lic = PlatformLicense.get()
        lic.status = PlatformLicense.LicenseStatus.GRACE
        lic.last_verified_at = timezone.now() - timedelta(days=2)
        lic.save()
        # 7 - 2 = 5 days remaining (floor to int days)
        assert lic.grace_days_remaining == 5
