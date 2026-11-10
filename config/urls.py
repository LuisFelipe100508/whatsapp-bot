from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from .views import health

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("webhook/", include("apps.whatsapp.urls")),
    path("cron/", include("apps.notifications.urls")),
    path("health/", health, name="health"),
]