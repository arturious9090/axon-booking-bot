import asyncio
from datetime import timedelta

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.methods import EditMessageText, GetMe, SendMessage
from aiogram.types import Message, Update, User
from django.utils import timezone

from booking.models import Appointment
from telegram_bot.handlers import router

pytestmark = pytest.mark.django_db(transaction=True)
dispatcher = Dispatcher()
dispatcher.include_router(router)


class RecordingSession(BaseSession):
    """Exercise actual aiogram routing without contacting Telegram."""

    def __init__(self):
        super().__init__()
        self.requests = []

    async def close(self):
        pass

    async def make_request(self, bot, method, timeout=None):
        self.requests.append(method)
        if isinstance(method, GetMe):
            return User(id=123456, is_bot=True, first_name="Demo", username="axon_test_bot")
        if isinstance(method, (SendMessage, EditMessageText)):
            return Message.model_validate(
                {
                    "message_id": 10,
                    "date": timezone.now(),
                    "chat": {"id": 1001, "type": "private"},
                    "text": method.text,
                    "reply_markup": method.reply_markup,
                },
                context={"bot": bot},
            )
        return True

    async def stream_content(self, url, **kwargs):
        yield b""


@pytest.fixture
def conversation():
    session = RecordingSession()
    bot = Bot("123456:TEST_TOKEN_DO_NOT_USE", session=session)

    def send(data, user_id=1001, *, command=False):
        message = {
            "message_id": 10,
            "date": timezone.now(),
            "chat": {"id": user_id, "type": "private"},
            "text": data if command else "Кнопки",
            "from": {"id": user_id, "is_bot": False, "first_name": "Тестовый клиент"},
        }
        payload = {"update_id": len(session.requests) + 1}
        if command:
            message["entities"] = [{"type": "bot_command", "offset": 0, "length": len(data)}]
            payload["message"] = message
        else:
            payload["callback_query"] = {
                "id": str(len(session.requests) + 1),
                "chat_instance": "demo",
                "data": data,
                "from": message["from"],
                "message": message,
            }
        update = Update.model_validate(payload, context={"bot": bot})
        asyncio.run(dispatcher.feed_update(bot, update))
        return [
            method
            for method in session.requests
            if isinstance(method, (SendMessage, EditMessageText))
        ][-1]

    return send


def test_full_bot_booking_move_and_cancel(catalog, conversation):
    service, specialist, _, starts_at = catalog
    assert "демонстрационный" in conversation("/start", command=True).text
    assert "Выберите услугу" in conversation("services").text
    assert specialist.name in str(conversation(f"service:{service.pk}").reply_markup)
    assert "Выберите дату" in conversation(f"dates:{service.pk}:{specialist.pk}").text
    response = conversation(f"day:{service.pk}:{specialist.pk}:{starts_at:%Y%m%d}")
    assert response.reply_markup.inline_keyboard[0][0].callback_data.startswith("slot:")
    confirmation = conversation(f"slot:{service.pk}:{specialist.pk}:{int(starts_at.timestamp())}")
    confirm_data = confirmation.reply_markup.inline_keyboard[0][0].callback_data
    assert len(confirm_data.encode()) <= 64
    assert "подтверждена" in conversation(confirm_data).text
    assert "подтверждена" in conversation(confirm_data).text  # Repeated callback.
    assert Appointment.objects.count() == 1
    appointment = Appointment.objects.get()
    assert "ближайшие записи" in conversation("my").text
    assert "Выберите дату" in conversation(f"move:{appointment.pk.hex}").text
    new_start = starts_at + timedelta(hours=1)
    confirmation = conversation(f"mslot:{appointment.pk.hex}:{int(new_start.timestamp())}")
    data = confirmation.reply_markup.inline_keyboard[0][0].callback_data
    assert len(data.encode()) <= 64
    assert "перенесена" in conversation(data).text
    appointment.refresh_from_db()
    assert appointment.starts_at == new_start
    assert "Отменить эту запись" in conversation(f"cancel:{appointment.pk.hex}").text
    assert "отменена" in conversation(f"cancelok:{appointment.pk.hex}").text
    appointment.refresh_from_db()
    assert appointment.status == "cancelled"


def test_bot_rejects_another_users_cancel(catalog, conversation):
    from booking.services import create_appointment

    service, specialist, client, starts_at = catalog
    appointment = create_appointment(
        client=client, service_id=service.pk, specialist_id=specialist.pk, starts_at=starts_at
    )
    assert "не найдена" in conversation(f"cancelok:{appointment.pk.hex}", user_id=999).text
    appointment.refresh_from_db()
    assert appointment.status == "confirmed"


def test_invalid_callback_is_handled(conversation):
    assert "устарела" in conversation("slot:broken").text
