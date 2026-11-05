from django.db import models


class Reminder(models.Model):
    class Channel(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"
        EMAIL = "email", "E-mail"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        SENT = "sent", "Enviado"
        FAILED = "failed", "Falhou"

    appointment = models.ForeignKey(
        "scheduling.Appointment", on_delete=models.CASCADE, related_name="reminders"
    )
    channel = models.CharField(max_length=10, choices=Channel.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.CharField(max_length=200, blank=True)  # sem dados pessoais
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "lembrete"
        verbose_name_plural = "lembretes"
        constraints = [
            # Garante idempotência: no máximo um lembrete por agendamento e canal,
            # mesmo que o cron rode duas vezes ou em paralelo.
            models.UniqueConstraint(fields=["appointment", "channel"], name="unique_reminder_per_channel")
        ]

    def __str__(self):
        return f"Lembrete {self.get_channel_display()} ({self.get_status_display()})"