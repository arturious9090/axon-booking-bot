import pytest
from django.core.management import call_command
from django.test import override_settings

from booking.models import Appointment
from booking.services import create_appointment

pytestmark = pytest.mark.django_db


def test_home_and_health(client, catalog):
    with override_settings(
        STORAGES={
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}
        }
    ):
        response = client.get("/")
    assert response.status_code == 200
    assert "Стрижка" in response.content.decode()
    assert "демо" in response.content.decode().lower()
    assert client.get("/health/").json() == {"status": "ok"}
    assert client.get("/admin/").status_code == 302


def test_admin_cannot_bypass_booking_logic(admin_client, catalog):
    service, specialist, customer, starts_at = catalog
    appointment = create_appointment(
        client=customer, service_id=service.pk, specialist_id=specialist.pk, starts_at=starts_at
    )
    assert admin_client.get("/admin/booking/appointment/add/").status_code == 403
    assert (
        admin_client.get(f"/admin/booking/appointment/{appointment.pk}/change/").status_code == 200
    )
    admin_client.post(
        "/admin/booking/appointment/",
        {
            "action": "cancel_selected",
            "_selected_action": [str(appointment.pk)],
        },
    )
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.CANCELLED


def test_django_configuration_and_migrations():
    call_command("check")
    call_command("makemigrations", check=True, dry_run=True)
