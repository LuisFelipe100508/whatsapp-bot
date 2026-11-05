from django.contrib import admin

from apps.businesses.models import Business, Service
from apps.customers.models import Customer


class OwnerScopedAdmin(admin.ModelAdmin):
    """Dono só vê (e só escolhe em formulários) dados do próprio negócio."""

    # Caminho do model até o dono. Cada admin ajusta se precisar.
    owner_lookup = "business__owner"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(**{self.owner_lookup: request.user})

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Impede o dono de escolher, num <select>, itens de outro negócio.
        if not request.user.is_superuser:
            scoped = {
                "business": Business.objects.filter(owner=request.user),
                "service": Service.objects.filter(business__owner=request.user),
                "customer": Customer.objects.filter(business__owner=request.user),
            }
            if db_field.name in scoped:
                kwargs["queryset"] = scoped[db_field.name]
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class ReadOnlyAdminMixin:
    """Só consulta: sem criar, editar ou apagar."""

    def has_add_permission(self, request, *args, **kwargs):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False