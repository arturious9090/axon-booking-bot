from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.utils import timezone

from booking.models import Notification
from booking.notifications import deliver_notification
from booking.services import cancel_appointment, create_appointment, reschedule_appointment

pytestmark = pytest.mark.django_db


@pytest.fixture
def due_notification(catalog):
    service, specialist, client, starts_at = catalog
    appointment = create_appointment(
        client=client, service_id=service.pk, specialist_id=specialist.pk, starts_at=starts_at
    )
    notification = Notification.objects.filter(appointment=appointment).first()
    notification.due_at = timezone.now() - timedelta(seconds=1)
    notification.save()
    return notification


def test_delivered_only_once(due_notification):
    sender = Mock()
    deliver_notification(due_notification.pk, sender)
    deliver_notification(due_notification.pk, sender)
    due_notification.refresh_from_db()
    assert due_notification.status == "sent"
    assert due_notification.attempts == 1
    sender.assert_called_once()


def test_cancelled_appointment_never_reminded(due_notification):
    cancel_appointment(
        appointment_id=due_notification.appointment_id,
        telegram_id=due_notification.appointment.client.telegram_id,
    )
    sender = Mock()
    deliver_notification(due_notification.pk, sender)
    due_notification.refresh_from_db()
    assert due_notification.status == "skipped"
    sender.assert_not_called()


def test_old_reminder_skipped_after_move(due_notification):
    appointment = due_notification.appointment
    reschedule_appointment(
        appointment_id=appointment.pk,
        telegram_id=appointment.client.telegram_id,
        starts_at=appointment.starts_at + timedelta(hours=1),
        expected_revision=1,
    )
    sender = Mock()
    deliver_notification(due_notification.pk, sender)
    due_notification.refresh_from_db()
    assert due_notification.status == "skipped"
    sender.assert_not_called()


def test_no_token_keeps_reminder_pending(due_notification, settings):
    settings.TELEGRAM_BOT_TOKEN = ""
    sender = Mock()
    deliver_notification(due_notification.pk, sender)
    due_notification.refresh_from_db()
    assert due_notification.status == "pending"
    assert due_notification.attempts == 0
    sender.assert_not_called()


def test_network_error_is_retried_without_logging_payload(due_notification):
    deliver_notification(due_notification.pk, Mock(side_effect=OSError("sensitive message")))
    due_notification.refresh_from_db()
    assert due_notification.status == "pending"
    assert due_notification.due_at > timezone.now()
    assert due_notification.last_error == "OSError"


def test_retry_limit(due_notification):
    due_notification.attempts = 4
    due_notification.save()
    deliver_notification(due_notification.pk, Mock(side_effect=OSError()))
    due_notification.refresh_from_db()
    assert due_notification.status == "failed"


def test_admin_notifications(catalog, settings):
    settings.TELEGRAM_ADMIN_CHAT_ID = "123"
    service, specialist, client, starts_at = catalog
    appointment = create_appointment(
        client=client, service_id=service.pk, specialist_id=specialist.pk, starts_at=starts_at
    )
    notification = Notification.objects.get(appointment=appointment, kind="admin_created")
    sender = Mock()
    deliver_notification(notification.pk, sender)
    assert sender.call_args.args[0] == "123"
    assert str(appointment.pk) in sender.call_args.args[1]


def test_admin_cancellation_notifies_client(due_notification):
    appointment = cancel_appointment(
        appointment_id=due_notification.appointment_id, telegram_id=None
    )
    notification = Notification.objects.get(appointment=appointment, kind="client_cancelled")
    sender = Mock()
    deliver_notification(notification.pk, sender)
    assert sender.call_args.args[0] == appointment.client.telegram_id
    assert "отменена администратором" in sender.call_args.args[1]
