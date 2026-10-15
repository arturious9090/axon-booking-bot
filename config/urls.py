from django.contrib import admin
from django.urls import path

from booking.views import health, home

admin.site.site_header = "Axon · управление записью"
admin.site.site_title = "Axon Studio"
admin.site.index_title = "Расписание и услуги"
urlpatterns = [
    path("", home, name="home"),
    path("health/", health),
    path("admin/", admin.site.urls),
]
