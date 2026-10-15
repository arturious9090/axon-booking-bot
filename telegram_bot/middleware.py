from aiogram import BaseMiddleware
from asgiref.sync import sync_to_async
from django.db import close_old_connections


class DatabaseConnectionMiddleware(BaseMiddleware):
    """Polling has no Django request lifecycle, so close expired DB connections explicitly."""

    async def __call__(self, handler, event, data):
        await sync_to_async(close_old_connections)()
        try:
            return await handler(event, data)
        finally:
            await sync_to_async(close_old_connections)()
