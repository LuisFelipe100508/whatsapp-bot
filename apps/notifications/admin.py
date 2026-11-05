from django.contrib import admin

from apps.businesses.admin_mixins import OwnerScopedAdmin, ReadOnlyAdminMixin

from .models import Reminder


@admin.register(Reminder)
class ReminderAdmin(ReadOnlyAdminMixin, OwnerScopedAdmin):
    owner_lookup = "appointment__business__owner"
    list_display = ("appointment", "channel", "status", "attempts", "sent_at")
    list_filter = ("channel", "status")