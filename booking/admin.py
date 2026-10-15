from django.contrib import admin, messages
from django.db import transaction

from .models import Appointment, Client, Notification, Service, Specialist, TimeOff, WorkingPeriod
from .services import BookingError, cancel_appointment


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["name", "duration_minutes", "price", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name"]


class WorkingPeriodInline(admin.TabularInline):
    model = WorkingPeriod
    extra = 0


@admin.register(Specialist)
class SpecialistAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active"]
    list_filter = ["is_active"]
    filter_horizontal = ["services"]
    inlines = [WorkingPeriodInline]

    def save_model(self, request, obj, form, change):
        if change:
            Specialist.objects.select_for_update().get(pk=obj.pk)
        super().save_model(request, obj, form, change)


@admin.register(TimeOff)
class TimeOffAdmin(admin.ModelAdmin):
    list_display = ["specialist", "starts_at", "ends_at", "reason"]
    list_filter = ["specialist"]

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            Specialist.objects.select_for_update().get(pk=obj.specialist_id)
            # Existing appointments stay intact when a schedule changes.
            super().save_model(request, obj, form, change)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ["name", "telegram_id", "created_at"]
    search_fields = ["name", "telegram_id"]
    readonly_fields = ["name", "telegram_id", "created_at"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ["starts_at", "ends_at", "client", "service", "specialist", "status", "price"]
    list_filter = ["status", "specialist", "service"]
    date_hierarchy = "starts_at"
    search_fields = ["client__name", "client__telegram_id"]
    list_select_related = ["client", "service", "specialist"]
    readonly_fields = [field.name for field in Appointment._meta.fields]
    actions = ["cancel_selected"]

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
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["appointment", "kind", "due_at", "status", "attempts", "last_error"]
    list_filter = ["status", "kind"]
    readonly_fields = [field.name for field in Notification._meta.fields]
    list_select_related = ["appointment__client", "appointment__service"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
