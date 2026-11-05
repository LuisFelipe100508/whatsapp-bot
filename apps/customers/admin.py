from django.contrib import admin

from apps.businesses.admin_mixins import OwnerScopedAdmin, ReadOnlyAdminMixin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(ReadOnlyAdminMixin, OwnerScopedAdmin):
    list_display = ("__str__", "email", "consent_at")  # __str__ já mascara o telefone
    search_fields = ("name", "phone")

    def has_delete_permission(self, request, obj=None):
        # Pedido de exclusão (LGPD) é tratado pelo superusuário.
        return request.user.is_superuser