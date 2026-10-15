import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Создать локального demo_admin со случайным паролем (только при DEBUG=true)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Демопользователь доступен только при DJANGO_DEBUG=true.")
        user_model = get_user_model()
        if user_model.objects.filter(username="demo_admin").exists():
            raise CommandError("demo_admin уже существует; его пароль не изменён.")
        password = secrets.token_urlsafe(18)
        user_model.objects.create_superuser(username="demo_admin", password=password)
        self.stdout.write(
            f"Логин: demo_admin\nПароль: {password}\nВход: http://localhost:8000/admin/"
        )
