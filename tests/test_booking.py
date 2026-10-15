from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, time, timedelta
from threading import Barrier

import pytest
from django.conf import settings
from django.core.management import call_command
from django.db import IntegrityError, close_old_connections, transaction
from django.utils import timezone

from booking.models import Appointment, Client, Notification, Service, Specialist, TimeOff
from booking.services import (
    BookingError,
    available_slots,
    booking_dates,
    cancel_appointment,
    create_appointment,
    reschedule_appointment,
)

pytestmark = pytest.mark.django_db


def book(catalog, **kwargs):
    service, specialist, client, starts_at = catalog
    return create_appointment(
        **{
            "client": client,
            "service_id": service.pk,
            "specialist_id": specialist.pk,
            "starts_at": starts_at,
        }
        | kwargs
    )


def test_booking_has_price_duration_and_reminders(catalog):
    appointment = book(catalog)
    assert appointment.ends_at - appointment.starts_at == timedelta(hours=1)
    assert appointment.price == catalog[0].price
    assert set(Notification.objects.values_list("kind", flat=True)) == {
        "reminder_24h",
        "reminder_2h",
    }
    assert not available_slots(catalog[0].pk, catalog[1].pk, catalog[3].date()).count(catalog[3])


def test_repeated_confirmation_is_idempotent(catalog):
    first = book(catalog, request_key="same-button")
    assert book(catalog, request_key="same-button").pk == first.pk
    assert Appointment.objects.count() == 1
    assert Notification.objects.count() == 2


def test_client_cannot_reuse_someone_elses_confirmation(catalog):
    book(catalog, request_key="same-button")
    other = Client.objects.create(telegram_id=1002, name="Другой")
    with pytest.raises(BookingError):
        book(catalog, client=other, request_key="same-button")


def test_overlapping_duration_rejected_and_adjacent_allowed(catalog):
    appointment = book(catalog)
    with pytest.raises(BookingError):
        book(catalog, starts_at=appointment.starts_at + timedelta(minutes=30))
    adjacent = book(catalog, starts_at=appointment.ends_at)
    assert adjacent.starts_at == appointment.ends_at


def test_postgres_constraint_rejects_overlaps_outside_service(catalog):
    appointment = book(catalog)
    with pytest.raises(IntegrityError), transaction.atomic():
        Appointment.objects.create(
            client=appointment.client,
            service=appointment.service,
            specialist=appointment.specialist,
            starts_at=appointment.starts_at + timedelta(minutes=15),
            ends_at=appointment.ends_at,
            price=appointment.price,
            request_key="bypass-service",
        )


@pytest.mark.parametrize("delta", [timedelta(days=-1), timedelta(days=15), timedelta(minutes=1)])
def test_unavailable_times_rejected(catalog, delta):
    with pytest.raises(BookingError):
        book(catalog, starts_at=timezone.now() + delta)


def test_naive_time_rejected(catalog):
    with pytest.raises(BookingError):
        book(catalog, starts_at=catalog[3].replace(tzinfo=None))


def test_lunch_and_timeoff_remove_slots(catalog):
    service, specialist, _, starts_at = catalog
    TimeOff.objects.create(
        specialist=specialist, starts_at=starts_at, ends_at=starts_at + timedelta(hours=1)
    )
    slots = available_slots(service.pk, specialist.pk, starts_at.date())
    local_times = [slot.astimezone(settings.STUDIO_TZ).time() for slot in slots]
    assert time(10) not in local_times
    assert time(12, 15) not in local_times  # A 60-minute service would cross the lunch break.
    assert time(13) not in local_times
    assert time(14) in local_times


def test_inactive_or_unassigned_specialist_rejected(catalog):
    catalog[1].services.clear()
    with pytest.raises(BookingError):
        book(catalog)
    catalog[1].services.add(catalog[0])
    catalog[1].is_active = False
    catalog[1].save()
    with pytest.raises(BookingError):
        book(catalog)


def test_reschedule_releases_old_time_and_preserves_snapshot(catalog):
    appointment = book(catalog)
    old_start = appointment.starts_at
    catalog[0].duration_minutes = 30
    catalog[0].price = 99
    catalog[0].save()
    moved = reschedule_appointment(
        appointment_id=appointment.pk,
        telegram_id=catalog[2].telegram_id,
        starts_at=old_start + timedelta(hours=1),
        expected_revision=1,
    )
    assert moved.revision == 2
    assert moved.price == 45
    assert moved.ends_at - moved.starts_at == timedelta(hours=1)
    assert book(catalog).starts_at == old_start
    assert Notification.objects.filter(appointment=moved, revision=2).count() == 2


def test_failed_reschedule_keeps_original_slot(catalog):
    original = book(catalog)
    occupied = book(catalog, starts_at=original.ends_at)
    with pytest.raises(BookingError):
        reschedule_appointment(
            appointment_id=original.pk,
            telegram_id=catalog[2].telegram_id,
            starts_at=occupied.starts_at,
            expected_revision=1,
        )
    original.refresh_from_db()
    assert original.starts_at == catalog[3]
    assert original.revision == 1


def test_stale_move_confirmation_is_rejected(catalog):
    appointment = book(catalog)
    reschedule_appointment(
        appointment_id=appointment.pk,
        telegram_id=catalog[2].telegram_id,
        starts_at=catalog[3] + timedelta(hours=1),
        expected_revision=1,
    )
    with pytest.raises(BookingError):
        reschedule_appointment(
            appointment_id=appointment.pk,
            telegram_id=catalog[2].telegram_id,
            starts_at=catalog[3] + timedelta(hours=4),
            expected_revision=1,
        )


def test_cancel_releases_slot_and_is_idempotent(catalog):
    appointment = book(catalog)
    for _ in range(2):
        cancelled = cancel_appointment(
            appointment_id=appointment.pk, telegram_id=catalog[2].telegram_id
        )
        assert cancelled.status == "cancelled"
        assert cancelled.revision == 2
    assert book(catalog).starts_at == catalog[3]


def test_other_client_cannot_cancel_or_move(catalog):
    appointment = book(catalog)
    with pytest.raises(BookingError):
        cancel_appointment(appointment_id=appointment.pk, telegram_id=999)
    with pytest.raises(BookingError):
        reschedule_appointment(
            appointment_id=appointment.pk,
            telegram_id=999,
            starts_at=catalog[3] + timedelta(hours=1),
            expected_revision=1,
        )


def test_close_booking_has_no_past_reminders(catalog):
    book(catalog, starts_at=timezone.now() + timedelta(hours=2))
    assert Notification.objects.count() == 0


def test_dst_duration_and_horizon(catalog, monkeypatch):
    monkeypatch.setattr(timezone, "now", lambda: datetime(2026, 10, 24, 6, tzinfo=UTC))
    day = date(2026, 10, 25)
    slots = available_slots(catalog[0].pk, catalog[1].pk, day)
    assert slots[0] == datetime(2026, 10, 25, 8, tzinfo=UTC)  # Berlin now UTC+1.
    assert len(booking_dates()) == 14


def test_seed_demo_is_repeatable():
    call_command("seed_demo")
    call_command("seed_demo")
    assert Service.objects.count() == 3
    assert Specialist.objects.count() == 3
    assert Appointment.objects.count() == 0
    assert Client.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_two_clients_racing_for_same_slot_only_one_succeeds(catalog):
    service, specialist, client, starts_at = catalog
    other = Client.objects.create(telegram_id=2002, name="Другой")
    barrier = Barrier(2)

    def attempt(client_id):
        close_old_connections()
        try:
            local_client = Client.objects.get(pk=client_id)
            barrier.wait(timeout=10)
            create_appointment(
                client=local_client,
                service_id=service.pk,
                specialist_id=specialist.pk,
                starts_at=starts_at,
            )
            return "booked"
        except BookingError:
            return "occupied"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, [client.pk, other.pk]))
    assert sorted(results) == ["booked", "occupied"]
    assert Appointment.objects.count() == 1
