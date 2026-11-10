from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("webhook/", include("apps.whatsapp.urls")),
    path("cron/", include("apps.notifications.urls")),
]