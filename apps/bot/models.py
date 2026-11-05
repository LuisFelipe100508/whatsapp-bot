from django.db import models


class BotReply(models.Model):
    class Intent(models.TextChoices):
        GREETING = "greeting", "Saudação / menu"
        HOURS = "hours", "Horário de funcionamento"
        PRICES = "prices", "Preços"
        ADDRESS = "address", "Endereço"
        FALLBACK = "fallback", "Não entendi"

    business = models.ForeignKey(
        "businesses.Business", on_delete=models.CASCADE, related_name="bot_replies"
    )
    intent = models.CharField("assunto", max_length=20, choices=Intent.choices)
    keywords = models.TextField(
        "palavras-chave",
        blank=True,
        help_text="Separadas por vírgula. Ex.: horário, abre, funciona",
    )
    text = models.TextField(
        "resposta",
        help_text="Pode usar {horarios}, {precos} e {endereco}: o bot preenche com os dados reais.",
    )
    is_active = models.BooleanField("ativa", default=True)

    class Meta:
        verbose_name = "resposta do bot"
        verbose_name_plural = "respostas do bot"
        constraints = [
            models.UniqueConstraint(fields=["business", "intent"], name="unique_reply_per_intent")
        ]

    def __str__(self):
        return f"{self.get_intent_display()} - {self.business}"