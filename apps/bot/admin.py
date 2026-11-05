from django.contrib import admin

from apps.businesses.admin_mixins import OwnerScopedAdmin

from .models import BotReply


@admin.register(BotReply)
class BotReplyAdmin(OwnerScopedAdmin):
    list_display = ("business", "intent", "is_active")
    list_filter = ("intent", "is_active")