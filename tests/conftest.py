from datetime import UTC, datetime, time, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from booking.models import Client, Service, Specialist, WorkingPeriod


@pytest.fixture(autouse=True)
def studio_settings(settings, monkeypatch):
    settings.TELEGRAM_BOT_TOKEN = "123456:TEST_TOKEN_DO_NOT_USE"
    settings.TELEGRAM_ADMIN_CHAT_ID = ""
    instant = datetime(2026, 10, 15, 6, tzinfo=UTC)
    monkeypatch.setattr(timezone, "now", lambda: instant)


@pytest.fixture
def catalog(db):
    service = Service.objects.create(name="Консультация", duration_minutes=60, price=Decimal("45"))
    specialist = Specialist.objects.create(name="Анна")
    specialist.services.add(service)
    for day in range(7):
        WorkingPeriod.objects.create(
            specialist=specialist, weekday=day, start_time=time(9), end_time=time(13)
        )
        WorkingPeriod.objects.create(
            specialist=specialist, weekday=day, start_time=time(14), end_time=time(18)
        )
    client = Client.objects.create(telegram_id=1001, name="Тестовый клиент")
    start = timezone.now() + timedelta(days=1, hours=2)  # 10:00 studio time tomorrow.
    return service, specialist, client, start
