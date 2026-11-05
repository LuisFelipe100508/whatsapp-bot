from django.core.validators import RegexValidator
from django.db import models

phone_validator = RegexValidator(
    r"^\d{8,15}$",
    "Use apenas dígitos, com código do país (ex.: 5535999999999).",
)


class Customer(models.Model):
    business = models.ForeignKey(
        "businesses.Business", on_delete=models.CASCADE, related_name="customers"
    )
    phone = models.CharField("telefone (WhatsApp)", max_length=15, validators=[phone_validator])
    name = models.CharField("nome", max_length=120, blank=True)
    email = models.EmailField("e-mail", blank=True)
    consent_at = models.DateTimeField("consentimento em", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "cliente"
        verbose_name_plural = "clientes"
        constraints = [
            models.UniqueConstraint(fields=["business", "phone"], name="unique_customer_phone_per_business")
        ]

    def __str__(self):
        # Telefone mascarado: se este objeto cair num log ou traceback, não vaza dado pessoal.
        return f"{self.name or 'Cliente'} (***{self.phone[-4:]})"