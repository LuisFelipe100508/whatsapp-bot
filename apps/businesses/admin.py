from django.contrib import admin

from .admin_mixins import OwnerScopedAdmin
from .models import Business, BusinessHours, Service

admin.site.site_header = "Painel do Negócio"
admin.site.site_title = "Painel do Negócio"
admin.site.index_title = "Gerenciar atendimento"


class ServiceInline(admin.TabularInline):
    model = Service
    extra = 0


class BusinessHoursInline(admin.TabularInline):
    model = BusinessHours
    extra = 0


@admin.register(Business)
class BusinessAdmin(OwnerScopedAdmin):
    owner_lookup = "owner"
    list_display = ("name", "phone", "is_active")
    inlines = [ServiceInline, BusinessHoursInline]

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return ()
        # O dono não pode trocar de dono nem apontar para outro número da Meta.
        return ("owner", "whatsapp_phone_number_id")

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser