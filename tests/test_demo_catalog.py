from datetime import UTC, datetime, time, timedelta

import pytest
from django.core.management import call_command

from booking.models import Appointment, Client, Service, Specialist, WorkingPeriod

pytestmark = pytest.mark.django_db


def legacy_service(**overrides):
    return Service.objects.create(
        **{
            "name": "Стрижка и укладка",
            "duration_minutes": 60,
            "price": 45,
            "description": "Новая форма и укладка под ваш ритм жизни.",
        }
        | overrides
    )


def test_refresh_preserves_ids_assignments_and_custom_catalog():
    legacy = legacy_service()
    custom = Service.objects.create(name="Своя услуга", duration_minutes=30, price=75)
    specialist = Specialist.objects.create(
        name="Анна", description="Стилист. Внимание к деталям и естественным формам."
    )
    specialist.services.add(legacy, custom)
    period = WorkingPeriod.objects.create(
        specialist=specialist, weekday=0, start_time=time(11), end_time=time(16)
    )
    own_specialist = Specialist.objects.create(name="Свой специалист", description="Моё описание")
    own_specialist.services.add(custom)
    for _ in range(2):
        call_command("seed_demo", refresh_examples=True)
    legacy.refresh_from_db()
    assert legacy.name == "Индивидуальная сессия"
    assert set(specialist.services.values_list("pk", flat=True)) == {legacy.pk, custom.pk}
    assert list(specialist.periods.values_list("pk", flat=True)) == [period.pk]
    assert Service.objects.get(pk=custom.pk).name == "Своя услуга"
    assert Specialist.objects.get(pk=own_specialist.pk).description == "Моё описание"
    assert Service.objects.count() == 4


def test_refresh_does_not_overwrite_edited_examples():
    legacy = legacy_service(description="Изменено вручную")
    specialist = Specialist.objects.create(name="Анна", description="Своё описание")
    specialist.services.add(legacy)
    call_command("seed_demo", refresh_examples=True)
    legacy.refresh_from_db()
    specialist.refresh_from_db()
    assert legacy.name == "Стрижка и укладка"
    assert legacy.description == "Изменено вручную"
    assert specialist.description == "Своё описание"
    assert list(specialist.services.all()) == [legacy]


def test_refresh_preserves_booked_service_and_appointment_history():
    legacy = legacy_service()
    specialist = Specialist.objects.create(name="Своя команда")
    specialist.services.add(legacy)
    client = Client.objects.create(name="Тестовый клиент", telegram_id=1001)
    start = datetime(2026, 10, 16, 8, tzinfo=UTC)
    appointment = Appointment.objects.create(
        client=client,
        service=legacy,
        specialist=specialist,
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        price=45,
        request_key="legacy-confirmation",
    )
    call_command("seed_demo", refresh_examples=True)
    legacy.refresh_from_db()
    appointment.refresh_from_db()
    assert legacy.name == "Стрижка и укладка"
    assert appointment.service_id == legacy.pk
    assert appointment.status == "confirmed"
    assert appointment.starts_at == start
    assert appointment.price == 45
