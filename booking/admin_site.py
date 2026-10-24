from django.conf import settings
from django.contrib.admin import AdminSite
from django.urls import reverse

from .calendar import calendar_context


class AxonAdminSite(AdminSite):
    index_template = "admin/axon_index.html"
    site_header = "Axon · управление записью"
    site_title = "Axon · запись на услуги"
    index_title = "Расписание"
    enable_nav_sidebar = True

    def each_context(self, request):
        context = super().each_context(request)
        calendar_allowed = request.user.has_perm(
            "booking.view_appointment"
        ) or request.user.has_perm("booking.change_appointment")
        available = {
            model["object_name"].lower(): model
            for app in context["available_apps"]
            for model in app["models"]
        }
        navigation = []
        if calendar_allowed:
            url = reverse("admin:index")
            navigation.append(
                {
                    "label": "Расписание",
                    "url": url,
                    "icon": "calendar",
                    "active": request.path == url,
                }
            )
        for name, label, icon in [
            ("appointment", "Записи", "list"),
            ("service", "Услуги", "grid"),
            ("specialist", "Специалисты", "users"),
            ("timeoff", "Перерывы и отсутствие", "clock"),
            ("client", "Клиенты", "user"),
            ("notification", "Уведомления", "bell"),
        ]:
            if name in available and available[name].get("admin_url"):
                url = available[name]["admin_url"]
                navigation.append(
                    {
                        "label": label,
                        "url": url,
                        "icon": icon,
                        "active": request.path.startswith(url),
                    }
                )
        context.update(
            {
                "axon_navigation": navigation,
                "calendar_allowed": calendar_allowed,
                "axon_company": settings.STUDIO_NAME,
                "axon_service_url": available.get("service", {}).get("admin_url"),
                "axon_specialist_url": available.get("specialist", {}).get("admin_url"),
                "axon_appointment_url": available.get("appointment", {}).get("admin_url"),
                "axon_access_navigation": [
                    {
                        "label": model["name"],
                        "url": model["admin_url"],
                        "icon": "users" if model["object_name"] == "Group" else "user",
                        "active": request.path.startswith(model["admin_url"]),
                    }
                    for app in context["available_apps"]
                    if app["app_label"] != "booking"
                    for model in app["models"]
                    if model.get("admin_url")
                ],
            }
        )
        return context

    def index(self, request, extra_context=None):
        allowed = request.user.has_perm("booking.view_appointment") or request.user.has_perm(
            "booking.change_appointment"
        )
        context = calendar_context(request) if allowed else {}
        return super().index(request, {**context, **(extra_context or {})})
