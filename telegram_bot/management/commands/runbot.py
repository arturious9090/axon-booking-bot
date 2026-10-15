import asyncio

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from telegram_bot.handlers import router


class Command(BaseCommand):
    help = "Запустить Telegram-бота в режиме long polling (ровно один экземпляр)."

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_TOKEN:
            raise CommandError("Задайте TELEGRAM_BOT_TOKEN в .env.")
        asyncio.run(self.run())

    async def run(self):
        async with Bot(settings.TELEGRAM_BOT_TOKEN) as bot:
            await bot.set_my_commands(
                [
                    BotCommand(command="start", description="Главное меню"),
                    BotCommand(command="book", description="Записаться"),
                    BotCommand(command="my", description="Мои записи"),
                    BotCommand(command="help", description="Как работает демо"),
                ]
            )
            dispatcher = Dispatcher()
            dispatcher.include_router(router)
            await dispatcher.start_polling(bot, close_bot_session=False)
