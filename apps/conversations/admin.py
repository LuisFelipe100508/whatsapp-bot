from django.contrib import admin

from apps.businesses.admin_mixins import OwnerScopedAdmin, ReadOnlyAdminMixin

from .models import Conversation, Message


class MessageInline(ReadOnlyAdminMixin, admin.TabularInline):
    model = Message
    extra = 0
    can_delete = False
    fields = ("created_at", "direction", "body")
    readonly_fields = fields


@admin.register(Conversation)
class ConversationAdmin(ReadOnlyAdminMixin, OwnerScopedAdmin):
    owner_lookup = "customer__business__owner"
    list_display = ("customer", "state", "updated_at")
    list_filter = ("state",)
    fields = ("customer", "state", "created_at", "updated_at")
    inlines = [MessageInline]