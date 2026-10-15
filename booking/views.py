from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from .models import Service, Specialist


def home(request):
    return render(
        request,
        "booking/home.html",
        {
            "studio_name": settings.STUDIO_NAME,
            "studio_timezone": settings.TIME_ZONE,
            "bot_username": settings.TELEGRAM_BOT_USERNAME,
            "services": Service.objects.filter(is_active=True),
            "specialists": Specialist.objects.filter(is_active=True).prefetch_related("services"),
        },
    )


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
