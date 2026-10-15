import secrets
from datetime import UTC, date, datetime, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Appointment, Client, Notification, Service, Specialist, TimeOff


class BookingError(ValueError):
    """An expected business error that can safely be displayed to the user."""


def booking_dates():
    today = timezone.localdate(timezone=settings.STUDIO_TZ)
    return [today + timedelta(days=i) for i in range(settings.BOOKING_HORIZON_DAYS)]


def available_slots(service_id, specialist_id, day: date, *, exclude=None, duration=None):
    if day not in booking_dates():
        return []
    service = Service.objects.filter(pk=service_id, is_active=True).first()
    specialist = Specialist.objects.filter(
        pk=specialist_id, is_active=True, services__id=service_id
    ).first()
    if not service or not specialist:
        return []
    duration = duration or timedelta(minutes=service.duration_minutes)
    # Iterate in UTC: durations remain elapsed minutes across daylight saving changes.
    day_start = datetime.combine(day, datetime.min.time(), settings.STUDIO_TZ).astimezone(UTC)
    day_end = datetime.combine(
        day + timedelta(days=1), datetime.min.time(), settings.STUDIO_TZ
    ).astimezone(UTC)
    occupied = Appointment.objects.filter(
        specialist=specialist,
        status=Appointment.Status.CONFIRMED,
        starts_at__lt=day_end,
        ends_at__gt=day_start,
    )
    if exclude:
        occupied = occupied.exclude(pk=exclude)
    blocks = list(occupied.values_list("starts_at", "ends_at"))
    blocks += list(
        TimeOff.objects.filter(
            specialist=specialist, starts_at__lt=day_end, ends_at__gt=day_start
        ).values_list("starts_at", "ends_at")
    )
    now = timezone.now()
    slots = set()
    for period in specialist.periods.filter(weekday=day.weekday()):
        start = datetime.combine(day, period.start_time, settings.STUDIO_TZ).astimezone(UTC)
        end = datetime.combine(day, period.end_time, settings.STUDIO_TZ).astimezone(UTC)
        while start + duration <= end:
            if start > now and not any(
                start < b_end and start + duration > b for b, b_end in blocks
            ):
                slots.add(start)
            start += timedelta(minutes=settings.SLOT_STEP_MINUTES)
    return sorted(slots)


def get_client(telegram_id: int, name: str):
    client, _ = Client.objects.update_or_create(
        telegram_id=telegram_id, defaults={"name": name[:160]}
    )
    return client


def _schedule_notifications(appointment, admin_kind):
    now = timezone.now()
    if appointment.status == Appointment.Status.CONFIRMED:
        for kind, hours in [
            (Notification.Kind.REMINDER_24H, 24),
            (Notification.Kind.REMINDER_2H, 2),
        ]:
            due_at = appointment.starts_at - timedelta(hours=hours)
            if due_at > now:
                Notification.objects.create(
                    appointment=appointment, revision=appointment.revision, kind=kind, due_at=due_at
                )
    if settings.TELEGRAM_ADMIN_CHAT_ID:
        Notification.objects.create(
            appointment=appointment, revision=appointment.revision, kind=admin_kind, due_at=now
        )


def _validate_slot(service_id, specialist_id, starts_at, **kwargs):
    if timezone.is_naive(starts_at):
        raise BookingError("Время записи должно содержать часовой пояс.")
    day = starts_at.astimezone(settings.STUDIO_TZ).date()
    if starts_at not in available_slots(service_id, specialist_id, day, **kwargs):
        raise BookingError("Это время уже недоступно. Выберите другой слот.")


@transaction.atomic
def create_appointment(*, client, service_id, specialist_id, starts_at, request_key=None):
    # All booking mutations for a specialist are serialized. The database exclusion
    # constraint is the final safeguard, including for writes outside this service.
    specialist = Specialist.objects.select_for_update().filter(pk=specialist_id).first()
    if not specialist:
        raise BookingError("Специалист недоступен.")
    request_key = request_key or secrets.token_hex(16)
    existing = Appointment.objects.filter(request_key=request_key).first()
    if existing:
        if existing.client_id != client.pk:
            raise BookingError("Эта кнопка недоступна. Начните новую запись.")
        return existing
    _validate_slot(service_id, specialist_id, starts_at)
    service = Service.objects.get(pk=service_id, is_active=True)
    try:
        with transaction.atomic():
            appointment = Appointment.objects.create(
                client=client,
                service=service,
                specialist=specialist,
                starts_at=starts_at,
                ends_at=starts_at + timedelta(minutes=service.duration_minutes),
                price=service.price,
                request_key=request_key,
            )
    except IntegrityError as error:
        raise BookingError("Это время уже занято. Выберите другой слот.") from error
    _schedule_notifications(appointment, Notification.Kind.ADMIN_CREATED)
    return appointment


def _locked_appointment(appointment_id, telegram_id=None):
    queryset = Appointment.objects.all()
    if telegram_id is not None:
        queryset = queryset.filter(client__telegram_id=telegram_id)
    reference = queryset.filter(pk=appointment_id).values("specialist_id").first()
    if not reference:
        raise BookingError("Запись не найдена.")
    Specialist.objects.select_for_update().get(pk=reference["specialist_id"])
    return queryset.select_for_update().get(pk=appointment_id)


@transaction.atomic
def reschedule_appointment(*, appointment_id, telegram_id, starts_at, expected_revision):
    appointment = _locked_appointment(appointment_id, telegram_id)
    if (
        appointment.status != Appointment.Status.CONFIRMED
        or appointment.starts_at <= timezone.now()
    ):
        raise BookingError("Эту запись уже нельзя перенести.")
    if appointment.starts_at == starts_at:
        return appointment
    if appointment.revision != expected_revision:
        raise BookingError("Запись уже изменилась. Откройте «Мои записи».")
    duration = appointment.ends_at - appointment.starts_at
    _validate_slot(
        appointment.service_id,
        appointment.specialist_id,
        starts_at,
        exclude=appointment.pk,
        duration=duration,
    )
    appointment.starts_at = starts_at
    appointment.ends_at = starts_at + duration
    appointment.revision += 1
    try:
        with transaction.atomic():
            appointment.save(update_fields=["starts_at", "ends_at", "revision", "updated_at"])
    except IntegrityError as error:
        raise BookingError("Это время уже занято. Выберите другой слот.") from error
    _schedule_notifications(appointment, Notification.Kind.ADMIN_MOVED)
    return appointment


@transaction.atomic
def cancel_appointment(*, appointment_id, telegram_id):
    # telegram_id=None is reserved for the authenticated Django admin action.
    appointment = _locked_appointment(appointment_id, telegram_id)
    if appointment.status == Appointment.Status.CANCELLED:
        return appointment
    if appointment.starts_at <= timezone.now():
        raise BookingError("Нельзя отменить уже начавшийся визит.")
    appointment.status = Appointment.Status.CANCELLED
    appointment.revision += 1
    appointment.save(update_fields=["status", "revision", "updated_at"])
    _schedule_notifications(appointment, Notification.Kind.ADMIN_CANCELLED)
    if telegram_id is None:
        Notification.objects.create(
            appointment=appointment,
            revision=appointment.revision,
            kind=Notification.Kind.CLIENT_CANCELLED,
            due_at=timezone.now(),
        )
    return appointment
