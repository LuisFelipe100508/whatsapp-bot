from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeBoundary, RangeOperators
from django.db import models
from django.db.models import F, Func, Q


class TsTzRange(Func):
    function = "TSTZRANGE"
    output_field = DateTimeRangeField()


class Appointment(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmado"
        CANCELLED = "cancelled", "Cancelado"
        COMPLETED = "completed", "Concluído"
        NO_SHOW = "no_show", "Não compareceu"

    business = models.ForeignKey(
        "businesses.Business", on_delete=models.CASCADE, related_name="appointments"
    )
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.CASCADE, related_name="appointments"
    )
    # RESTRICT: não deixa apagar um serviço que tem agendamentos (desative-o),
    # mas permite apagar o negócio inteiro, que leva tudo junto.
    service = models.ForeignKey(
        "businesses.Service", on_delete=models.RESTRICT, related_name="appointments"
    )
    start_at = models.DateTimeField("início")
    end_at = models.DateTimeField("fim")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CONFIRMED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "agendamento"
        verbose_name_plural = "agendamentos"
        ordering = ["start_at"]
        indexes = [models.Index(fields=["business", "start_at"], name="appt_business_start_idx")]
        constraints = [
            models.CheckConstraint(condition=Q(end_at__gt=F("start_at")), name="appt_end_after_start"),
            # O PostgreSQL recusa dois agendamentos CONFIRMADOS do mesmo negócio
            # com intervalos que se sobrepõem. Vale mesmo com requisições simultâneas.
            ExclusionConstraint(
                name="no_overlapping_confirmed_appointments",
                expressions=[
                    (TsTzRange("start_at", "end_at", RangeBoundary()), RangeOperators.OVERLAPS),
                    ("business", RangeOperators.EQUAL),
                ],
                condition=Q(status="confirmed"),
            ),
        ]

    def __str__(self):
        return f"Agendamento #{self.pk} em {self.start_at:%d/%m %H:%M}"