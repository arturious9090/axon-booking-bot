from datetime import date, time, timedelta

import pytest
from django.contrib.auth.models import Permission, User
from django.templatetags.static import static
from django.test import Client as WebClient

from booking.models import Appointment, Notification, Specialist, TimeOff
from booking.services import cancel_appointment, create_appointment

pytestmark = pytest.mark.django_db


@pytest.fixture
def appointment(catalog):
    service, specialist, client, starts_at = catalog
    return create_appointment(
        client=client, service_id=service.pk, specialist_id=specialist.pk, starts_at=starts_at
    )


def test_calendar_shows_week_and_links_to_real_appointment(admin_client, appointment):
    response = admin_client.get("/admin/?week=2026-10-16")
    assert response.status_code == 200
    assert response.context["week_start"] == date(2026, 10, 12)
    assert response.context["visit_count"] == 1
    assert len(response.context["calendar_days"]) == 7
    html = response.content.decode()
    assert appointment.client.name in html
    assert f"/admin/booking/appointment/{appointment.pk}/change/" in html
    assert static("booking/admin.css") in html


def test_calendar_filters_cancelled_and_specialist(admin_client, appointment):
    other = Specialist.objects.create(name="Другой специалист")
    response = admin_client.get(f"/admin/?specialist={other.pk}")
    assert response.context["visit_count"] == 0
    assert len(response.context["calendar_rows"]) == 1
    cancel_appointment(appointment_id=appointment.pk, telegram_id=appointment.client.telegram_id)
    assert not admin_client.get("/admin/").context["has_visits"]
    response = admin_client.get("/admin/?cancelled=1")
    assert response.context["has_visits"]
    assert response.context["visit_count"] == 0
    assert "Отменена" in response.content.decode()


@pytest.mark.parametrize("week", ["invalid", "9999-12-31", "0001-01-01"])
def test_calendar_handles_bad_or_boundary_dates(admin_client, week):
    response = admin_client.get("/admin/", {"week": week, "specialist": "9999999999999999999999"})
    assert response.status_code == 200
    assert response.context["week_start"] == date(2026, 10, 12)
    assert response.context["selected_specialist"] == ""


def test_absence_is_visible_in_both_calendar_views(admin_client, catalog):
    starts_at = catalog[3] - timedelta(hours=12)
    TimeOff.objects.create(
        specialist=catalog[1],
        starts_at=starts_at,
        ends_at=starts_at + timedelta(days=3),
        reason="Не должно раскрываться на главной",
    )
    html = admin_client.get("/admin/").content.decode()
    assert "Недоступен весь день" in html
    assert "Не должно раскрываться на главной" not in html
    assert 'class="calendar-absence"' in html


def test_calendar_does_not_expose_clients_without_appointment_permission(client, appointment):
    staff = User.objects.create_user(username="services-only", password="test", is_staff=True)
    staff.user_permissions.add(Permission.objects.get(codename="view_service"))
    client.force_login(staff)
    response = client.get("/admin/")
    assert response.status_code == 200
    assert not response.context["calendar_allowed"]
    assert appointment.client.name not in response.content.decode()


def test_cancel_requires_confirmation_permission_and_csrf(admin_client, appointment):
    url = f"/admin/booking/appointment/{appointment.pk}/cancel/"
    assert admin_client.get(url).status_code == 200
    appointment.refresh_from_db()
    assert appointment.status == "confirmed"
    staff = User.objects.create_user(username="readonly", password="test", is_staff=True)
    staff.user_permissions.add(Permission.objects.get(codename="view_appointment"))
    viewer = WebClient()
    viewer.force_login(staff)
    assert viewer.post(url).status_code == 403
    csrf_client = WebClient(enforce_csrf_checks=True)
    csrf_client.force_login(User.objects.get(username="admin"))
    assert csrf_client.post(url).status_code == 403
    assert admin_client.post(url).status_code == 302
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.CANCELLED
    assert (
        Notification.objects.filter(appointment=appointment, kind="client_cancelled").count() == 1
    )
    assert admin_client.post(url).status_code == 302
    assert (
        Notification.objects.filter(appointment=appointment, kind="client_cancelled").count() == 1
    )


def test_working_hours_can_be_saved_with_native_time_inputs(admin_client, catalog):
    response = admin_client.post(
        "/admin/booking/specialist/add/",
        {
            "name": "Ирина",
            "description": "",
            "is_active": "on",
            "services": [catalog[0].pk],
            "periods-TOTAL_FORMS": "1",
            "periods-INITIAL_FORMS": "0",
            "periods-MIN_NUM_FORMS": "0",
            "periods-MAX_NUM_FORMS": "1000",
            "periods-0-weekday": "0",
            "periods-0-start_time": "09:30",
            "periods-0-end_time": "16:45",
            "_save": "Сохранить",
        },
    )
    assert response.status_code == 302
    period = Specialist.objects.get(name="Ирина").periods.get()
    assert period.start_time == time(9, 30)
    assert period.end_time == time(16, 45)
