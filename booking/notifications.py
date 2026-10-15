import asyncio
import logging
from datetime import timedelta

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Appointment, Notification

logger = logging.getLogger(__name__)


def appointment_text(appointment):
    local = appointment.starts_at.astimezone(settings.STUDIO_TZ)
    end = appointment.ends_at.astimezone(settings.STUDIO_TZ)
    return (
        f"{appointment.service.name}\n"
        f"Специалист: {appointment.specialist.name}\n"
        f"{local:%d.%m.%Y}, {local:%H:%M}–{end:%H:%M} ({settings.TIME_ZONE})\n"
        f"Стоимость: {appointment.price:.2f} EUR"
    )


async def _send(chat_id, text):
    async with Bot(settings.TELEGRAM_BOT_TOKEN, session=AiohttpSession(timeout=10)) as bot:
        await bot.send_message(chat_id, text)


def send_telegram(chat_id, text):
    # No parse mode: names and descriptions from Telegram are always plain text.
    asyncio.run(_send(chat_id, text))


def deliver_notification(notification_id, sender=send_telegram):
    reference = Notification.objects.filter(pk=notification_id).values("appointment_id").first()
    if not reference:
        return
    with transaction.atomic():
        # Lock the appointment before the notification, consistently with cancellation.
        # A completed cancellation therefore cannot race with a reminder status check.
        appointment = (
            Appointment.objects.select_for_update(of=("self",))
            .select_related("service", "specialist", "client")
            .get(pk=reference["appointment_id"])
        )
        notification = Notification.objects.select_for_update().get(pk=notification_id)
        now = timezone.now()
        if notification.status != Notification.Status.PENDING or notification.due_at > now:
            return
        reminder = notification.kind.startswith("reminder_")
        if appointment.revision != notification.revision or (
            reminder
            and (appointment.status != Appointment.Status.CONFIRMED or appointment.starts_at <= now)
        ):
            notification.status = Notification.Status.SKIPPED
            notification.save(update_fields=["status"])
            return
        if not settings.TELEGRAM_BOT_TOKEN:
            return  # Keep pending; configuring the bot must not silently discard reminders.
        client_message = reminder or notification.kind == Notification.Kind.CLIENT_CANCELLED
        chat_id = (
            appointment.client.telegram_id if client_message else settings.TELEGRAM_ADMIN_CHAT_ID
        )
        if not chat_id:
            notification.status = Notification.Status.SKIPPED
            notification.save(update_fields=["status"])
            return
        prefix = "Напоминаем о визите" if reminder else notification.get_kind_display()
        text = f"{settings.STUDIO_NAME} · {prefix}\n\n{appointment_text(appointment)}"
        if not client_message:
            text += f"\nКлиент: {appointment.client.name}\nЗапись: {appointment.pk}"
        notification.attempts += 1
        try:
            sender(chat_id, text)
        except Exception as error:
            # Store the exception class only: API messages can contain personal data or tokens.
            notification.last_error = type(error).__name__
            permanent = isinstance(error, (TelegramForbiddenError, TelegramBadRequest))
            notification.status = (
                Notification.Status.FAILED
                if permanent or notification.attempts >= 5
                else Notification.Status.PENDING
            )
            delay = (
                error.retry_after
                if isinstance(error, TelegramRetryAfter)
                else min(60 * 2**notification.attempts, 3600)
            )
            notification.due_at = now + timedelta(seconds=delay)
            logger.warning("Notification %s: %s", notification.pk, type(error).__name__)
        else:
            notification.status = Notification.Status.SENT
            notification.sent_at = timezone.now()
            notification.last_error = ""
        notification.save()
