from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q


class Business(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="businesses",
        verbose_name="dono",
    )
    name = models.CharField("nome", max_length=120)
    address = models.CharField("endereço", max_length=255, blank=True)
    phone = models.CharField("telefone", max_length=30, blank=True)
    whatsapp_phone_number_id = models.CharField(
        "ID do número no WhatsApp (Meta)",
        max_length=50,
        unique=True,
        help_text="Aparece no painel da Meta. É assim que o webhook descobre de qual negócio é a mensagem.",
    )
    reminder_hours_before = models.PositiveSmallIntegerField(
        "lembrete (horas antes)",
        default=24,
        validators=[MinValueValidator(1), MaxValueValidator(72)],
    )
    is_active = models.BooleanField("ativo", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "negócio"
        verbose_name_plural = "negócios"

    def __str__(self):
        return self.name


class Service(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="services")
    name = models.CharField("nome", max_length=100)
    price = models.DecimalField(
        "preço", max_digits=8, decimal_places=2, validators=[MinValueValidator(0)]
    )
    duration_minutes = models.PositiveSmallIntegerField(
        "duração (min)", validators=[MinValueValidator(5), MaxValueValidator(480)]
    )
    is_active = models.BooleanField("ativo", default=True)

    class Meta:
        verbose_name = "serviço"
        verbose_name_plural = "serviços"
        constraints = [
            models.UniqueConstraint(
                fields=["business", "name"], name="unique_service_name_per_business"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.duration_minutes} min)"


class BusinessHours(models.Model):
    class Weekday(models.IntegerChoices):  # mesmo padrão do datetime.weekday()
        MONDAY = 0, "Segunda-feira"
        TUESDAY = 1, "Terça-feira"
        WEDNESDAY = 2, "Quarta-feira"
        THURSDAY = 3, "Quinta-feira"
        FRIDAY = 4, "Sexta-feira"
        SATURDAY = 5, "Sábado"
        SUNDAY = 6, "Domingo"

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="hours")
    weekday = models.PositiveSmallIntegerField("dia da semana", choices=Weekday.choices)
    opens_at = models.TimeField("abre às")
    closes_at = models.TimeField("fecha às")

    class Meta:
        verbose_name = "horário de funcionamento"
        verbose_name_plural = "horários de funcionamento"
        ordering = ["business", "weekday"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "weekday"], name="unique_hours_per_weekday"
            ),
            models.CheckConstraint(
                condition=Q(closes_at__gt=F("opens_at")), name="hours_close_after_open"
            ),
        ]

    def __str__(self):
        return f"{self.get_weekday_display()}: {self.opens_at:%H:%M}-{self.closes_at:%H:%M}"