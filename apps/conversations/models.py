from django.db import models


class Conversation(models.Model):
    class State(models.TextChoices):
        IDLE = "idle", "Início"
        CHOOSING_SERVICE = "choosing_service", "Escolhendo serviço"
        CHOOSING_DATE = "choosing_date", "Escolhendo dia"
        CHOOSING_TIME = "choosing_time", "Escolhendo horário"
        ASKING_EMAIL = "asking_email", "Pedindo e-mail"
        CONFIRMING = "confirming", "Confirmando"

    customer = models.OneToOneField(
        "customers.Customer", on_delete=models.CASCADE, related_name="conversation"
    )
    state = models.CharField(max_length=20, choices=State.choices, default=State.IDLE)
    # Escolhas temporárias do fluxo (ids, data). Nunca guardar dado pessoal aqui.
    context = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "conversa"
        verbose_name_plural = "conversas"

    def __str__(self):
        return f"Conversa #{self.pk} ({self.get_state_display()})"


class Message(models.Model):
    class Direction(models.TextChoices):
        IN = "in", "Recebida"
        OUT = "out", "Enviada"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    direction = models.CharField(max_length=3, choices=Direction.choices)
    body = models.TextField("texto")
    # ID da mensagem na Meta. A Meta reenvia webhooks; o unique evita processar duas vezes.
    # null=True é intencional: o unique do Postgres aceita vários NULL (mensagens enviadas por nós).
    wa_message_id = models.CharField(max_length=128, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "mensagem"
        verbose_name_plural = "mensagens"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.get_direction_display()} #{self.pk}"  # nunca inclui o texto