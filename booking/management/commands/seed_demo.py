from datetime import time
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from booking.models import Service, Specialist, WorkingPeriod


class Command(BaseCommand):
    help = "Добавить вымышленные услуги и специалистов (без клиентов, паролей и записей)."

    @transaction.atomic
    def handle(self, *args, **options):
        services = []
        for name, minutes, price, description in [
            ("Стрижка и укладка", 60, "45.00", "Новая форма и укладка под ваш ритм жизни."),
            ("Маникюр", 45, "35.00", "Уход за руками и аккуратное покрытие."),
            ("Массаж спины", 30, "40.00", "Полчаса отдыха и восстановления."),
        ]:
            service, _ = Service.objects.get_or_create(
                name=name,
                defaults={
                    "duration_minutes": minutes,
                    "price": Decimal(price),
                    "description": description,
                },
            )
            services.append(service)
        for name, description, indexes in [
            ("Анна", "Стилист. Внимание к деталям и естественным формам.", [0]),
            ("Мария", "Мастер маникюра. Ухоженные руки каждый день.", [1]),
            ("Алексей", "Специалист по массажу. Помогает замедлиться и отдохнуть.", [2]),
        ]:
            specialist, created = Specialist.objects.get_or_create(
                name=name, defaults={"description": description}
            )
            if created:
                specialist.services.set([services[i] for i in indexes])
                for weekday in range(6):
                    for start, end in [(time(9), time(13)), (time(14), time(18))]:
                        WorkingPeriod.objects.create(
                            specialist=specialist, weekday=weekday, start_time=start, end_time=end
                        )
        self.stdout.write(
            self.style.SUCCESS(
                "Демокаталог готов: 3 услуги и 3 специалиста, "
                "Пн–Сб 09:00–18:00, перерыв 13:00–14:00."
            )
        )
