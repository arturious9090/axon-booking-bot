import logging
import secrets
from datetime import UTC, datetime
from uuid import UUID

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    ErrorEvent,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from asgiref.sync import sync_to_async
from django.conf import settings
from django.utils import timezone

from booking.models import Appointment, Service, Specialist
from booking.notifications import appointment_text
from booking.services import (
    BookingError,
    available_slots,
    booking_dates,
    cancel_appointment,
    create_appointment,
    get_client,
    reschedule_appointment,
)
from telegram_bot.middleware import DatabaseConnectionMiddleware

router = Router()
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")
router.message.outer_middleware(DatabaseConnectionMiddleware())
router.callback_query.outer_middleware(DatabaseConnectionMiddleware())
logger = logging.getLogger(__name__)


def keyboard(rows):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=data) for label, data in row]
            for row in rows
        ]
    )


def menu_keyboard():
    return keyboard(
        [
            [("Записаться", "services")],
            [("Мои записи", "my")],
        ]
    )


async def show(message, text, markup, *, edit=True):
    if edit:
        try:
            await message.edit_text(text, reply_markup=markup)
        except TelegramBadRequest as error:
            if "message is not modified" not in error.message:
                raise
    else:
        await message.answer(text, reply_markup=markup)


@router.message(CommandStart())
async def start(message: Message):
    await message.answer(
        f"{settings.STUDIO_NAME} · запись на услуги\n\n"
        "Выберите услугу, специалиста и удобное время. "
        "Перенести или отменить визит можно в разделе «Мои записи».\n\n"
        "Это демонстрационный проект Axon с вымышленной студией. "
        "При записи сохраним ваше имя и Telegram ID для управления визитом и напоминаний.",
        reply_markup=menu_keyboard(),
    )


@router.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        "Это демо: настоящие услуги не оказываются, оплата не требуется.\n"
        f"Всё время показано в часовом поясе {settings.TIME_ZONE}.\n"
        "Напоминания приходят за сутки и за 2 часа, если запись создана заранее.\n"
        "/book — записаться\n/my — мои записи\n/start — главное меню",
        reply_markup=menu_keyboard(),
    )


async def services_screen(message, *, edit=True):
    services = await sync_to_async(list)(Service.objects.filter(is_active=True))
    rows = [
        [(f"{s.name} · {s.duration_minutes} мин · {s.price:.2f} €", f"service:{s.pk}")]
        for s in services
    ]
    rows.append([("Мои записи", "my")])
    await show(
        message,
        "Выберите услугу:" if services else "Пока нет доступных услуг.",
        keyboard(rows),
        edit=edit,
    )


@router.message(Command("book"))
async def book_command(message: Message):
    await services_screen(message, edit=False)


@sync_to_async
def owned_appointment(appointment_id, telegram_id):
    appointment = (
        Appointment.objects.select_related("service", "specialist", "client")
        .filter(pk=UUID(appointment_id), client__telegram_id=telegram_id)
        .first()
    )
    if not appointment:
        raise BookingError("Запись не найдена.")
    return appointment


@sync_to_async
def upcoming(telegram_id):
    return list(
        Appointment.objects.select_related("service", "specialist", "client")
        .filter(
            client__telegram_id=telegram_id,
            status=Appointment.Status.CONFIRMED,
            starts_at__gt=timezone.now(),
        )
        .order_by("starts_at")[:20]
    )


async def my_screen(message, telegram_id):
    appointments = await upcoming(telegram_id)
    if not appointments:
        await message.answer("У вас пока нет предстоящих записей.", reply_markup=menu_keyboard())
        return
    for appointment in appointments:
        await message.answer(
            appointment_text(appointment),
            reply_markup=keyboard(
                [
                    [
                        ("Перенести", f"move:{appointment.pk.hex}"),
                        ("Отменить", f"cancel:{appointment.pk.hex}"),
                    ],
                ]
            ),
        )
    await message.answer("Это ваши ближайшие записи.", reply_markup=menu_keyboard())


@router.message(Command("my"))
async def my_command(message: Message):
    await my_screen(message, message.from_user.id)


async def days_screen(message, service_id, specialist_id, *, appointment=None):
    dates = booking_dates()
    prefix = f"mday:{appointment.pk.hex}" if appointment else f"day:{service_id}:{specialist_id}"
    buttons = [(day.strftime("%d.%m · %a"), f"{prefix}:{day:%Y%m%d}") for day in dates]
    # Explicit Russian weekday labels independent of operating system locale.
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    buttons = [
        (f"{day:%d.%m} · {weekdays[day.weekday()]}", data)
        for day, (_, data) in zip(dates, buttons, strict=True)
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append([("К услугам", "services"), ("Мои записи", "my")])
    await show(message, f"Выберите дату. Часовой пояс: {settings.TIME_ZONE}.", keyboard(rows))


async def slots_screen(message, service_id, specialist_id, day, *, appointment=None):
    options = {}
    if appointment:
        options = {
            "exclude": appointment.pk,
            "duration": appointment.ends_at - appointment.starts_at,
        }
    slots = await sync_to_async(available_slots)(service_id, specialist_id, day, **options)
    prefix = f"mslot:{appointment.pk.hex}" if appointment else f"slot:{service_id}:{specialist_id}"
    buttons = []
    for slot in slots:
        local = slot.astimezone(settings.STUDIO_TZ)
        # Offset disambiguates repeated wall-clock times at the DST boundary.
        buttons.append((f"{local:%H:%M %Z}", f"{prefix}:{int(slot.timestamp())}"))
    rows = [buttons[i : i + 3] for i in range(0, len(buttons), 3)]
    back = f"move:{appointment.pk.hex}" if appointment else f"dates:{service_id}:{specialist_id}"
    rows.append([("Другая дата", back), ("Меню", "home")])
    text = f"Свободное время на {day:%d.%m}:" if slots else "На эту дату свободного времени нет."
    await show(message, text, keyboard(rows))


@router.callback_query(F.data)
async def callback(query: CallbackQuery):
    await query.answer()
    if not isinstance(query.message, Message):
        return
    message = query.message
    parts = query.data.split(":")
    action = parts[0]
    user_id = query.from_user.id
    try:
        if action == "home":
            await show(message, "Что хотите сделать?", menu_keyboard())
        elif action == "services":
            await services_screen(message)
        elif action == "my":
            await my_screen(message, user_id)
        elif action == "service":
            service_id = int(parts[1])
            specialists = await sync_to_async(list)(
                Specialist.objects.filter(
                    is_active=True, services__id=service_id, services__is_active=True
                )
            )
            rows = [[(s.name, f"dates:{service_id}:{s.pk}")] for s in specialists]
            rows.append([("К услугам", "services")])
            await show(
                message,
                "Выберите специалиста:"
                if specialists
                else "Для этой услуги пока нет доступных специалистов.",
                keyboard(rows),
            )
        elif action == "dates":
            await days_screen(message, int(parts[1]), int(parts[2]))
        elif action == "day":
            await slots_screen(
                message, int(parts[1]), int(parts[2]), datetime.strptime(parts[3], "%Y%m%d").date()
            )
        elif action == "slot":
            service_id, specialist_id = int(parts[1]), int(parts[2])
            starts_at = datetime.fromtimestamp(int(parts[3]), UTC)
            service = await Service.objects.aget(pk=service_id, is_active=True)
            specialist = await Specialist.objects.aget(pk=specialist_id, is_active=True)
            local = starts_at.astimezone(settings.STUDIO_TZ)
            key = secrets.token_hex(8)
            await show(
                message,
                f"Подтвердите запись:\n\n{service.name}\n{specialist.name}\n"
                f"{local:%d.%m.%Y, %H:%M %Z}\n"
                f"{service.duration_minutes} мин · {service.price:.2f} EUR\n\n"
                "Время закрепляется после подтверждения.",
                keyboard(
                    [
                        [("Подтвердить", f"book:{service_id}:{specialist_id}:{parts[3]}:{key}")],
                        [("Другое время", f"day:{service_id}:{specialist_id}:{local:%Y%m%d}")],
                    ]
                ),
            )
        elif action == "book":
            client = await sync_to_async(get_client)(user_id, query.from_user.full_name)
            appointment = await sync_to_async(create_appointment)(
                client=client,
                service_id=int(parts[1]),
                specialist_id=int(parts[2]),
                starts_at=datetime.fromtimestamp(int(parts[3]), UTC),
                request_key=parts[4],
            )
            text = (
                "✅ Запись подтверждена."
                if appointment.status == "confirmed"
                else "Запись отменена."
            )
            # Load related objects in the synchronous ORM context.
            appointment = await owned_appointment(appointment.pk.hex, user_id)
            await show(message, f"{text}\n\n{appointment_text(appointment)}", menu_keyboard())
        elif action in {"move", "mday", "mslot", "mbook", "cancel", "cancelok"}:
            appointment = await owned_appointment(parts[1], user_id)
            if action in {"move", "mday", "mslot", "mbook"} and (
                appointment.status != "confirmed" or appointment.starts_at <= timezone.now()
            ):
                raise BookingError("Эту запись уже нельзя перенести.")
            if action == "move":
                await days_screen(
                    message,
                    appointment.service_id,
                    appointment.specialist_id,
                    appointment=appointment,
                )
            elif action == "mday":
                await slots_screen(
                    message,
                    appointment.service_id,
                    appointment.specialist_id,
                    datetime.strptime(parts[2], "%Y%m%d").date(),
                    appointment=appointment,
                )
            elif action == "mslot":
                local = datetime.fromtimestamp(int(parts[2]), settings.STUDIO_TZ)
                await show(
                    message,
                    f"Перенести «{appointment.service.name}» на {local:%d.%m.%Y, %H:%M %Z}?",
                    keyboard(
                        [
                            [
                                (
                                    "Подтвердить перенос",
                                    f"mbook:{appointment.pk.hex}:{parts[2]}:{appointment.revision}",
                                )
                            ],
                            [("Другая дата", f"move:{appointment.pk.hex}")],
                        ]
                    ),
                )
            elif action == "mbook":
                await sync_to_async(reschedule_appointment)(
                    appointment_id=appointment.pk,
                    telegram_id=user_id,
                    starts_at=datetime.fromtimestamp(int(parts[2]), UTC),
                    expected_revision=int(parts[3]),
                )
                appointment = await owned_appointment(parts[1], user_id)
                await show(
                    message,
                    f"✅ Запись перенесена.\n\n{appointment_text(appointment)}",
                    menu_keyboard(),
                )
            elif action == "cancel":
                await show(
                    message,
                    f"Отменить эту запись?\n\n{appointment_text(appointment)}",
                    keyboard(
                        [
                            [("Да, отменить", f"cancelok:{appointment.pk.hex}")],
                            [("Сохранить запись", "my")],
                        ]
                    ),
                )
            elif action == "cancelok":
                await sync_to_async(cancel_appointment)(
                    appointment_id=appointment.pk, telegram_id=user_id
                )
                await show(message, "Запись отменена. Можно выбрать новое время.", menu_keyboard())
        else:
            raise BookingError("Эта кнопка устарела. Начните с главного меню.")
    except BookingError as error:
        await message.answer(str(error), reply_markup=menu_keyboard())
    except (ValueError, IndexError, Service.DoesNotExist, Specialist.DoesNotExist):
        await message.answer(
            "Эта кнопка устарела. Выберите услугу заново.", reply_markup=menu_keyboard()
        )


@router.errors()
async def unexpected_error(event: ErrorEvent):
    logger.error("Bot update failed: %s", type(event.exception).__name__)
    query = event.update.callback_query
    message = query.message if query else event.update.message
    if isinstance(message, Message):
        await message.answer(
            "Не удалось выполнить действие. Попробуйте ещё раз через минуту.",
            reply_markup=menu_keyboard(),
        )
    return True


@router.message()
async def fallback(message: Message):
    await message.answer("Для записи воспользуйтесь кнопками ниже.", reply_markup=menu_keyboard())
