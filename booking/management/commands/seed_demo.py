from datetime import time
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from booking.models import Appointment, Service, Specialist, WorkingPeriod

SERVICE_EXAMPLES = [
    (
        "Индивидуальная сессия",
        60,
        "45.00",
        "Час совместной работы над вашим запросом.",
        "Стрижка и укладка",
        "Новая форма и укладка под ваш ритм жизни.",
    ),
    (
        "Разбор задачи",
        45,
        "35.00",
        "Обсудим детали задачи и наметим следующие шаги.",
        "Маникюр",
        "Уход за руками и аккуратное покрытие.",
    ),
    (
        "Консультация",
        30,
        "40.00",
        "Обсудим ваш вопрос и подходящий формат работы.",
        "Массаж спины",
        "Полчаса отдыха и восстановления.",
    ),
]


class Command(BaseCommand):
    help = "Добавить вымышленные услуги и специалистов (без клиентов, паролей и записей)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--refresh-examples",
            action="store_true",
            help=(
                "Заменить неизменённые примеры первой версии; "
                "сохранить свои данные и историю записей."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        services = []
        for name, minutes, price, description, old_name, old_description in SERVICE_EXAMPLES:
            if options["refresh_examples"] and not Service.objects.filter(name=name).exists():
                # Preserve edited examples and appointment history. Renaming a pristine
                # unused example keeps its ID and every specialist assignment intact.
                legacy = Service.objects.filter(
                    name=old_name,
                    description=old_description,
                    duration_minutes=minutes,
                    price=Decimal(price),
                    is_active=True,
                ).first()
                if legacy and not Appointment.objects.filter(service=legacy).exists():
                    legacy.name = name
                    legacy.description = description
                    legacy.save(update_fields=["name", "description"])
            service, _ = Service.objects.get_or_create(
                name=name,
                defaults={
                    "duration_minutes": minutes,
                    "price": Decimal(price),
                    "description": description,
                },
            )
            services.append(service)
        for name, description, indexes, old_description in [
            (
                "Анна",
                "Индивидуальные сессии по вашему запросу.",
                [0],
                "Стилист. Внимание к деталям и естественным формам.",
            ),
            (
                "Мария",
                "Разбор задач и планирование следующих шагов.",
                [1],
                "Мастер маникюра. Ухоженные руки каждый день.",
            ),
            (
                "Алексей",
                "Консультации и ответы на ваши вопросы.",
                [2],
                "Специалист по массажу. Помогает замедлиться и отдохнуть.",
            ),
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
            elif options["refresh_examples"] and specialist.description == old_description:
                specialist.description = description
                specialist.save(update_fields=["description"])
                specialist.services.add(*[services[i] for i in indexes])
        self.stdout.write(
            self.style.SUCCESS(
                "Демопримеры готовы: консультация, разбор задачи и индивидуальная сессия. "
                "Пользовательские данные и существующие записи сохранены."
            )
        )
