from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import Appointment, Client, Notification, Service, Specialist, TimeOff, WorkingPeriod
from .services import BookingError, cancel_appointment


class AxonModelAdmin(admin.ModelAdmin):
    """Task-oriented Russian titles instead of generated model-name sentences."""

    def changelist_view(self, request, extra_context=None):
        labels = {
            "service": "Добавить услугу",
            "specialist": "Добавить специалиста",
            "timeoff": "Добавить отсутствие",
        }
        return super().changelist_view(
            request,
            {
                "title": str(self.opts.verbose_name_plural).capitalize(),
                "axon_add_label": labels.get(self.opts.model_name, "Добавить"),
                **(extra_context or {}),
            },
        )

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        labels = {
            "service": ("Новая услуга", "Услуга"),
            "specialist": ("Новый специалист", "Специалист"),
            "timeoff": ("Новое отсутствие", "Отсутствие"),
        }
        titles = labels.get(
            self.opts.model_name,
            (str(self.opts.verbose_name).capitalize(), str(self.opts.verbose_name).capitalize()),
        )
        return super().changeform_view(
            request,
            object_id,
            form_url,
            {
                "title": titles[bool(object_id)],
                **(extra_context or {}),
            },
        )


@admin.register(Service)
class ServiceAdmin(AxonModelAdmin):
    list_display = ["name", "duration_label", "price_label", "availability"]
    list_filter = ["is_active"]
    search_fields = ["name"]
    fieldsets = [
        ("Об услуге", {"fields": ["name", "description"]}),
        ("Условия записи", {"fields": ["duration_minutes", "price", "is_active"]}),
    ]
    list_per_page = 25

    @admin.display(description="Длительность", ordering="duration_minutes")
    def duration_label(self, obj):
        return f"{obj.duration_minutes} мин"

    @admin.display(description="Стоимость", ordering="price")
    def price_label(self, obj):
        return f"{obj.price:.2f} EUR"

    @admin.display(description="Доступность", ordering="is_active")
    def availability(self, obj):
        return format_html(
            '<span class="status-badge {}">{}</span>',
            "" if obj.is_active else "inactive",
            "Доступна для записи" if obj.is_active else "Скрыта",
        )


class WorkingPeriodForm(forms.ModelForm):
    class Meta:
        model = WorkingPeriod
        fields = ["weekday", "start_time", "end_time"]
        widgets = {
            "weekday": forms.Select(attrs={"aria-label": "День недели"}),
            "start_time": forms.TimeInput(
                attrs={"type": "time", "aria-label": "Начало рабочего интервала"}, format="%H:%M"
            ),
            "end_time": forms.TimeInput(
                attrs={"type": "time", "aria-label": "Конец рабочего интервала"}, format="%H:%M"
            ),
        }


class WorkingPeriodInline(admin.TabularInline):
    model = WorkingPeriod
    form = WorkingPeriodForm
    extra = 0


@admin.register(Specialist)
class SpecialistAdmin(AxonModelAdmin):
    list_display = ["name", "is_active"]
    list_filter = ["is_active"]
    filter_horizontal = ["services"]
    inlines = [WorkingPeriodInline]
    search_fields = ["name"]
    fieldsets = [
        ("О специалисте", {"fields": ["name", "description", "is_active"]}),
        ("Услуги", {"fields": ["services"]}),
    ]
    list_per_page = 25

    def save_model(self, request, obj, form, change):
        if change:
            Specialist.objects.select_for_update().get(pk=obj.pk)
        super().save_model(request, obj, form, change)


@admin.register(TimeOff)
class TimeOffAdmin(AxonModelAdmin):
    list_display = ["specialist", "starts_at", "ends_at", "reason"]
    list_filter = ["specialist"]
    fieldsets = [
        (
            "Период отсутствия",
            {
                "fields": ["specialist", "starts_at", "ends_at", "reason"],
                "description": "Новые записи в этот период будут недоступны. "
                "Уже созданные визиты нужно перенести или отменить отдельно.",
            },
        ),
    ]

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            Specialist.objects.select_for_update().get(pk=obj.specialist_id)
            # Existing appointments stay intact when a schedule changes.
            super().save_model(request, obj, form, change)


@admin.register(Client)
class ClientAdmin(AxonModelAdmin):
    list_display = ["name", "telegram_id", "created_at"]
    search_fields = ["name", "telegram_id"]
    readonly_fields = ["name", "telegram_id", "created_at"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Appointment)
class AppointmentAdmin(AxonModelAdmin):
    list_display = ["starts_at", "ends_at", "client", "service", "specialist", "status_label"]
    list_filter = ["status", "specialist", "service"]
    date_hierarchy = "starts_at"
    search_fields = ["client__name", "client__telegram_id"]
    list_select_related = ["client", "service", "specialist"]
    readonly_fields = [
        "client",
        "service",
        "specialist",
        "starts_at",
        "ends_at",
        "price",
        "status",
        "created_at",
        "updated_at",
    ]
    fieldsets = [
        ("Визит", {"fields": ["service", "specialist", "starts_at", "ends_at", "price", "status"]}),
        ("Клиент", {"fields": ["client"]}),
        ("История записи", {"fields": ["created_at", "updated_at"]}),
    ]
    change_form_template = "admin/booking/appointment/change_form.html"
    list_per_page = 25
    actions = ["cancel_selected"]

    @admin.display(description="Статус", ordering="status")
    def status_label(self, obj):
        return format_html(
            '<span class="status-badge {}">{}</span>',
            "inactive" if obj.status == "cancelled" else "",
            obj.get_status_display(),
        )

    def get_urls(self):
        return [
            path(
                "<uuid:object_id>/cancel/",
                self.admin_site.admin_view(self.cancel_view),
                name="booking_appointment_cancel",
            )
        ] + super().get_urls()

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        obj = self.get_object(request, object_id) if object_id else None
        return super().changeform_view(
            request,
            object_id,
            form_url,
            {
                "can_cancel_appointment": bool(
                    obj
                    and obj.status == "confirmed"
                    and obj.starts_at > timezone.now()
                    and self.has_change_permission(request, obj)
                ),
                "show_save": False,
                "show_save_and_continue": False,
                "show_save_and_add_another": False,
                **(extra_context or {}),
            },
        )

    def cancel_view(self, request, object_id):
        obj = self.get_object(request, str(object_id))
        if obj is None:
            raise Http404
        if not self.has_change_permission(request, obj):
            raise PermissionDenied
        return_url = reverse("admin:booking_appointment_change", args=[obj.pk])
        if request.method == "POST":
            try:
                cancel_appointment(appointment_id=obj.pk, telegram_id=None)
            except BookingError as error:
                self.message_user(request, str(error), messages.ERROR)
            else:
                self.log_change(request, obj, "Запись отменена администратором.")
                self.message_user(
                    request, "Запись отменена. Клиент получит уведомление.", messages.SUCCESS
                )
            return HttpResponseRedirect(return_url)
        request.current_app = self.admin_site.name
        return TemplateResponse(
            request,
            "admin/booking/appointment/cancel.html",
            {
                **self.admin_site.each_context(request),
                "title": "Отменить запись",
                "appointment": obj,
                "return_url": return_url,
                "can_cancel": obj.status == "confirmed" and obj.starts_at > timezone.now(),
            },
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Отменить выбранные записи", permissions=["change"])
    def cancel_selected(self, request, queryset):
        count = 0
        for appointment in queryset:
            try:
                cancel_appointment(appointment_id=appointment.pk, telegram_id=None)
                count += 1
            except BookingError as error:
                self.message_user(request, str(error), messages.WARNING)
        self.message_user(request, f"Обработано записей: {count}.", messages.SUCCESS)


@admin.register(Notification)
class NotificationAdmin(AxonModelAdmin):
    list_display = ["appointment", "kind", "due_at", "status", "attempts", "last_error"]
    list_filter = ["status", "kind"]
    readonly_fields = [field.name for field in Notification._meta.fields]
    list_select_related = ["appointment__client", "appointment__service"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
