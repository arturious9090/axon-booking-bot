from datetime import UTC, date, datetime, timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from .models import Appointment, Specialist, TimeOff


def calendar_context(request):
    today = timezone.localdate(timezone=settings.STUDIO_TZ)
    try:
        selected = date.fromisoformat(request.GET.get("week", ""))
        monday = selected - timedelta(days=selected.weekday())
        # Reserve room for week navigation, including at year boundaries.
        monday - timedelta(days=7)
        monday + timedelta(days=14)
    except (ValueError, OverflowError):
        selected = today
        monday = today - timedelta(days=today.weekday())
    dates = [monday + timedelta(days=i) for i in range(7)]
    start = datetime.combine(monday, datetime.min.time(), settings.STUDIO_TZ).astimezone(UTC)
    end = datetime.combine(monday + timedelta(days=7), datetime.min.time(), settings.STUDIO_TZ)
    specialists = list(Specialist.objects.prefetch_related("periods").order_by("name"))
    selected_specialist = request.GET.get("specialist", "")
    selected_specialist = next(
        (str(s.pk) for s in specialists if str(s.pk) == selected_specialist), ""
    )
    visible = [
        s for s in specialists if not selected_specialist or str(s.pk) == selected_specialist
    ]
    show_cancelled = request.GET.get("cancelled") == "1"
    visits = (
        Appointment.objects.select_related("client", "service", "specialist")
        .filter(
            specialist__in=visible,
            starts_at__lt=end,
            ends_at__gt=start,
        )
        .order_by("starts_at", "client__name")
    )
    if not show_cancelled:
        visits = visits.filter(status=Appointment.Status.CONFIRMED)
    visits = list(visits)
    time_off = list(
        TimeOff.objects.filter(specialist__in=visible, starts_at__lt=end, ends_at__gt=start)
    )
    rows = []
    day_views = [
        {"date": day, "today": day == today, "entries": [], "hours": [], "absences": []}
        for day in dates
    ]
    for specialist in visible:
        cells = []
        for day_view in day_views:
            day = day_view["date"]
            day_start = datetime.combine(day, datetime.min.time(), settings.STUDIO_TZ)
            day_end = datetime.combine(
                day + timedelta(days=1), datetime.min.time(), settings.STUDIO_TZ
            )
            hours = [
                period for period in specialist.periods.all() if period.weekday == day.weekday()
            ]
            entries = []
            for visit in visits:
                if visit.specialist_id != specialist.pk or not (
                    visit.starts_at < day_end and visit.ends_at > day_start
                ):
                    continue
                entry = {
                    "visit": visit,
                    "url": reverse("admin:booking_appointment_change", args=[visit.pk]),
                }
                entries.append(entry)
                day_view["entries"].append(entry)
            absences = [
                absence
                for absence in time_off
                if absence.specialist_id == specialist.pk
                and absence.starts_at < day_end
                and absence.ends_at > day_start
            ]
            absence_labels = []
            for absence in absences:
                if absence.starts_at <= day_start and absence.ends_at >= day_end:
                    label = "Недоступен весь день"
                else:
                    local_start = max(absence.starts_at, day_start).astimezone(settings.STUDIO_TZ)
                    end_label = (
                        "24:00"
                        if absence.ends_at >= day_end
                        else absence.ends_at.astimezone(settings.STUDIO_TZ).strftime("%H:%M")
                    )
                    label = f"Недоступен {local_start:%H:%M}–{end_label}"
                absence_labels.append(label)
                day_view["absences"].append({"specialist": specialist, "label": label})
            cells.append(
                {
                    "date": day,
                    "today": day == today,
                    "hours": hours,
                    "entries": entries,
                    "absences": absence_labels,
                }
            )
            if hours:
                day_view["hours"].append({"specialist": specialist, "periods": hours})
        rows.append({"specialist": specialist, "cells": cells})
    for day_view in day_views:
        day_view["entries"].sort(key=lambda entry: entry["visit"].starts_at)
    filters = {}
    if selected_specialist:
        filters["specialist"] = selected_specialist
    if show_cancelled:
        filters["cancelled"] = "1"

    def week_url(day):
        return "?" + urlencode({**filters, "week": day.isoformat()})

    return {
        "week_start": monday,
        "week_end": dates[-1],
        "selected_day": selected,
        "calendar_days": day_views,
        "calendar_rows": rows,
        "calendar_specialists": specialists,
        "selected_specialist": selected_specialist,
        "show_cancelled": show_cancelled,
        "previous_week_url": week_url(monday - timedelta(days=7)),
        "next_week_url": week_url(monday + timedelta(days=7)),
        "current_week_url": week_url(today),
        "visit_count": sum(v.status == Appointment.Status.CONFIRMED for v in visits),
        "has_visits": bool(visits),
        "calendar_timezone": settings.TIME_ZONE,
    }
