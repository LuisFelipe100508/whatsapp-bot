from django import forms
from django.contrib import admin

from apps.businesses.admin_mixins import OwnerScopedAdmin

from .models import Appointment
from .services import has_conflict


class AppointmentAdminForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        appt = self.instance
        # Reativar um agendamento cancelado pode colidir com outro. Avisamos
        # com mensagem amigável (o banco continua sendo a barreira final).
        if (
            appt.pk
            and cleaned.get("status") == Appointment.Status.CONFIRMED
            and has_conflict(appt.business_id, appt.start_at, appt.end_at, exclude_pk=appt.pk)
        ):
            raise forms.ValidationError(
                "Esse horário já está ocupado por outro agendamento confirmado."
            )
        return cleaned


@admin.register(Appointment)
class AppointmentAdmin(OwnerScopedAdmin):
    form = AppointmentAdminForm
    list_display = ("start_at", "customer", "service", "status")
    list_filter = ("status",)
    list_select_related = ("customer", "service")
    date_hierarchy = "start_at"
    fields = ("business", "customer", "service", "start_at", "end_at", "status", "created_at", "updated_at")
    # Só o status é editável. Remarcar = cancelar e criar outro (evita conflito).
    readonly_fields = ("business", "customer", "service", "start_at", "end_at", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False  # agendamentos nascem pelo bot, via camada de serviços

    def has_delete_permission(self, request, obj=None):
        return False  # preserva o histórico: cancele em vez de apagar