import datetime as dt
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from apps.conversations.models import Message
from apps.scheduling.models import Appointment
from apps.whatsapp import client

from . import messages
from .models import Reminder

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
MAX_REMINDER_HOURS = 72  # mesmo teto do validador de Business.reminder_hours_before
WINDOW_24H = dt.timedelta(hours=24)

Channel = Reminder.Channel
Status = Reminder.Status


class ReminderSkipped(Exception):
    """Impossível enviar este lembrete e repetir não adianta (ex.: fora da janela de 24h)."""


# ---------------------------------------------------------------- e-mail

def _send_email(to: str, subject: str, body: str) -> None:
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to], fail_silently=False)


def send_confirmation_email(appointment) -> bool:
    """Melhor esforço: uma falha aqui nunca derruba o agendamento."""
    customer = appointment.customer
    if not customer.email:
        return False
    subject, body = messages.confirmation_email(appointment)
    try:
        _send_email(customer.email, subject, body)
    except Exception as exc:  # noqa: BLE001
        # Só o NOME da classe: a mensagem de um erro SMTP pode conter o e-mail do cliente.
        logger.error("notifications: falha no e-mail de confirmacao (%s)", type(exc).__name__)
        return False
    return True


# ---------------------------------------------------------------- entrega de lembretes

def _within_service_window(customer, now) -> bool:
    """O cliente escreveu nas últimas 24h? Então texto livre é permitido pela Meta."""
    return Message.objects.filter(
        conversation__customer=customer,
        direction=Message.Direction.IN,
        created_at__gte=now - WINDOW_24H,
    ).exists()


def _deliver_whatsapp(appointment, now) -> None:
    customer = appointment.customer
    phone_number_id = appointment.business.whatsapp_phone_number_id
    template = settings.WHATSAPP_REMINDER_TEMPLATE
    if template:
        client.send_template(
            phone_number_id=phone_number_id,
            to=customer.phone,
            template=template,
            language=settings.WHATSAPP_TEMPLATE_LANGUAGE,
            params=messages.template_params(appointment),
        )
    elif _within_service_window(customer, now):
        client.send_text(
            phone_number_id=phone_number_id,
            to=customer.phone,
            body=messages.reminder_whatsapp_text(appointment),
        )
    else:
        raise ReminderSkipped("fora da janela de 24h e sem template configurado")


def _deliver(channel, appointment, now) -> None:
    if channel == Channel.EMAIL:
        subject, body = messages.reminder_email(appointment)
        _send_email(appointment.customer.email, subject, body)
    else:
        _deliver_whatsapp(appointment, now)


def _safe_error(exc) -> str:
    name = type(exc).__name__
    if isinstance(exc, client.WhatsAppSendError):
        return f"{name}: {exc}"[:200]  # só código HTTP, por construção do client
    return name


def _attempt(reminder, appointment, now) -> str:
    """Uma tentativa de envio. Devolve: sent | retry | failed | skipped."""
    if reminder.channel == Channel.WHATSAPP and not settings.WHATSAPP_ACCESS_TOKEN:
        return "skipped"  # sem token (dev): o lembrete continua pendente, sem gastar tentativas

    # Compare-and-swap: só UMA execução do cron consegue reivindicar esta tentativa.
    claimed = Reminder.objects.filter(
        pk=reminder.pk, status=Status.PENDING, attempts=reminder.attempts
    ).update(attempts=reminder.attempts + 1)
    if not claimed:
        return "skipped"

    attempts = reminder.attempts + 1
    try:
        _deliver(reminder.channel, appointment, now)
    except ReminderSkipped as exc:
        Reminder.objects.filter(pk=reminder.pk).update(status=Status.FAILED, last_error=str(exc)[:200])
        return "failed"
    except Exception as exc:  # noqa: BLE001
        error = _safe_error(exc)
        final = attempts >= MAX_ATTEMPTS
        Reminder.objects.filter(pk=reminder.pk).update(
            status=Status.FAILED if final else Status.PENDING, last_error=error
        )
        logger.error("notifications: falha no lembrete (%s)", error)
        return "failed" if final else "retry"

    Reminder.objects.filter(pk=reminder.pk).update(status=Status.SENT, sent_at=timezone.now())
    return "sent"


def process_due_reminders(now=None) -> dict:
    """Envia os lembretes que já venceram. Seguro de rodar a qualquer momento, várias vezes."""
    now = now or timezone.now()
    result = {"sent": 0, "retry": 0, "failed": 0, "skipped": 0}

    candidates = (
        Appointment.objects.filter(
            status=Appointment.Status.CONFIRMED,
            business__is_active=True,
            start_at__gt=now,
            start_at__lte=now + dt.timedelta(hours=MAX_REMINDER_HOURS),
        )
        .select_related("business", "customer", "service")
        .order_by("start_at")
    )
    for appointment in candidates:
        remind_at = appointment.start_at - dt.timedelta(hours=appointment.business.reminder_hours_before)
        # Quem agendou DEPOIS do momento do lembrete acabou de receber a confirmação.
        if remind_at > now or appointment.created_at > remind_at:
            continue

        channels = [Channel.WHATSAPP]
        if appointment.customer.email:
            channels.append(Channel.EMAIL)
        for channel in channels:
            # A constraint unique(appointment, channel) garante um registro por canal.
            reminder, _ = Reminder.objects.get_or_create(appointment=appointment, channel=channel)
            if reminder.status != Status.PENDING:
                continue
            result[_attempt(reminder, appointment, now)] += 1

    logger.info("notifications: lembretes %s", result)
    return result