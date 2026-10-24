from django.contrib.admin.apps import AdminConfig


class AxonAdminConfig(AdminConfig):
    default_site = "booking.admin_site.AxonAdminSite"
