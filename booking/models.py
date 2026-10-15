import uuid

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeBoundary, RangeOperators
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Func, Q


class TimeRange(Func):
    function = "TSTZRANGE"
    output_field = DateTimeRangeField()


class Service(models.Model):
    name = models.CharField("название", max_length=120)
    description = models.TextField("описание", blank=True)
    duration_minutes = models.PositiveSmallIntegerField(
        "длительность, мин", validators=[MinValueValidator(15), MaxValueValidator(480)]
    )
    price = models.DecimalField(
        "стоимость, EUR", max_digits=8, decimal_places=2, validators=[MinValueValidator(0)]
    )
    is_active = models.BooleanField("доступна для записи", default=True)

    class Meta:
        verbose_name = "услуга"
        verbose_name_plural = "услуги"
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(duration_minutes__gte=15, duration_minutes__lte=480),
                name="service_valid_duration",
            ),
            models.CheckConstraint(condition=Q(price__gte=0), name="service_nonnegative_price"),
        ]

    def __str__(self):
        return f"{self.name} · {self.duration_minutes} мин"


class Specialist(models.Model):
    name = models.CharField("имя", max_length=120)
    description = models.TextField("о специалисте", blank=True)
    services = models.ManyToManyField(Service, verbose_name="услуги", related_name="specialists")
    is_active = models.BooleanField("доступен для записи", default=True)

    class Meta:
        verbose_name = "специалист"
        verbose_name_plural = "специалисты"
        ordering = ["name"]

    def __str__(self):
        return self.name


class WorkingPeriod(models.Model):
    WEEKDAYS = list(enumerate(["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]))
    specialist = models.ForeignKey(Specialist, on_delete=models.CASCADE, related_name="periods")
    weekday = models.PositiveSmallIntegerField("день недели", choices=WEEKDAYS)
    start_time = models.TimeField("начало")
    end_time = models.TimeField("конец")

    class Meta:
        verbose_name = "рабочий интервал"
        verbose_name_plural = "рабочие интервалы"
        ordering = ["weekday", "start_time"]
        constraints = [
            models.CheckConstraint(condition=Q(end_time__gt=F("start_time")), name="work_positive"),
            models.CheckConstraint(condition=Q(weekday__lte=6), name="work_valid_weekday"),
            models.UniqueConstraint(
                fields=["specialist", "weekday", "start_time"], name="work_unique_start"
            ),
        ]

    def __str__(self):
        return f"{self.get_weekday_display()} {self.start_time:%H:%M}–{self.end_time:%H:%M}"


class TimeOff(models.Model):
    specialist = models.ForeignKey(Specialist, on_delete=models.CASCADE, related_name="time_off")
    starts_at = models.DateTimeField("начало")
    ends_at = models.DateTimeField("конец")
    reason = models.CharField("причина", max_length=200, blank=True)

    class Meta:
        verbose_name = "перерыв / отсутствие"
        verbose_name_plural = "перерывы и отсутствие"
        ordering = ["starts_at"]
        constraints = [
            models.CheckConstraint(condition=Q(ends_at__gt=F("starts_at")), name="timeoff_positive")
        ]

    def __str__(self):
        return f"{self.specialist} · {self.starts_at:%d.%m.%Y}"


class Client(models.Model):
    telegram_id = models.BigIntegerField("Telegram ID", unique=True)
    name = models.CharField("имя в Telegram", max_length=160)
    created_at = models.DateTimeField("создан", auto_now_add=True)

    class Meta:
        verbose_name = "клиент"
        verbose_name_plural = "клиенты"

    def __str__(self):
        return self.name


class Appointment(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Подтверждена"
        CANCELLED = "cancelled", "Отменена"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, verbose_name="клиент")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, verbose_name="услуга")
    specialist = models.ForeignKey(Specialist, on_delete=models.PROTECT, verbose_name="специалист")
    starts_at = models.DateTimeField("начало")
    ends_at = models.DateTimeField("конец")
    price = models.DecimalField("стоимость при записи, EUR", max_digits=8, decimal_places=2)
    status = models.CharField("статус", max_length=16, choices=Status, default=Status.CONFIRMED)
    revision = models.PositiveIntegerField(default=1, editable=False)
    request_key = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField("создана", auto_now_add=True)
    updated_at = models.DateTimeField("обновлена", auto_now=True)

    class Meta:
        verbose_name = "запись"
        verbose_name_plural = "записи"
        ordering = ["starts_at"]
        constraints = [
            models.CheckConstraint(condition=Q(ends_at__gt=F("starts_at")), name="visit_positive"),
            ExclusionConstraint(
                name="no_overlapping_appointments",
                expressions=[
                    ("specialist", RangeOperators.EQUAL),
                    (TimeRange("starts_at", "ends_at", RangeBoundary()), RangeOperators.OVERLAPS),
                ],
                condition=Q(status="confirmed"),
            ),
        ]

    def __str__(self):
        return f"{self.client} · {self.service.name}"


class Notification(models.Model):
    class Kind(models.TextChoices):
        REMINDER_24H = "reminder_24h", "Напоминание за сутки"
        REMINDER_2H = "reminder_2h", "Напоминание за 2 часа"
        ADMIN_CREATED = "admin_created", "Администратору: новая запись"
        ADMIN_MOVED = "admin_moved", "Администратору: перенос"
        ADMIN_CANCELLED = "admin_cancelled", "Администратору: отмена"
        CLIENT_CANCELLED = "client_cancelled", "Запись отменена администратором"

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        SENT = "sent", "Отправлено"
        SKIPPED = "skipped", "Неактуально"
        FAILED = "failed", "Ошибка доставки"

    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE)
    revision = models.PositiveIntegerField()
    kind = models.CharField("тип", max_length=24, choices=Kind)
    due_at = models.DateTimeField("доставить после")
    status = models.CharField("статус", max_length=16, choices=Status, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField("попытки", default=0)
    sent_at = models.DateTimeField("отправлено", null=True, blank=True)
    last_error = models.CharField("последняя ошибка", max_length=100, blank=True)

    class Meta:
        verbose_name = "уведомление"
        verbose_name_plural = "уведомления"
        indexes = [models.Index(fields=["status", "due_at"], name="notification_due_idx")]
        constraints = [
            models.UniqueConstraint(
                fields=["appointment", "revision", "kind"], name="notification_once_per_revision"
            )
        ]

    def __str__(self):
        return self.get_kind_display()
