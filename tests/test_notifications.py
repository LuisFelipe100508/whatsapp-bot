import datetime as dt
import smtplib
from zoneinfo import ZoneInfo

import pytest

from apps.conversations.models import Conversation, Message
from apps.notifications import services
from apps.notifications.models import Reminder
from apps.scheduling.models import Appointment
from apps.whatsapp import client

pytestmark = pytest.mark.django_db

TZ = ZoneInfo("America/Sao_Paulo")
START = dt.datetime(2030, 1, 7, 10, 0, tzinfo=TZ)  # segunda-feira, 10:00
NOW_DUE = START - dt.timedelta(hours=23)    # o lembrete de 24h já venceu
NOW_EARLY = START - dt.timedelta(hours=30)  # ainda é cedo


@pytest.fixture
def appointment(business, service, customer):
    customer.email = "cliente@example.com"
    customer.save()
    return Appointment.objects.create(
        business=business, customer=customer, service=service,
        start_at=START, end_at=START + dt.timedelta(minutes=30),
    )


@pytest.fixture
def whatsapp(settings, monkeypatch):
    """Token configurado e a Meta 'falsa': registra o que seria enviado."""
    settings.WHATSAPP_ACCESS_TOKEN = "token-de-teste"
    settings.WHATSAPP_REMINDER_TEMPLATE = ""
    calls = {"text": [], "template": []}
    monkeypatch.setattr(client, "send_text", lambda **kw: calls["text"].append(kw) or True)
    monkeypatch.setattr(client, "send_template", lambda **kw: calls["template"].append(kw) or True)
    return calls


def channel_status(appointment, channel):
    return Reminder.objects.get(appointment=appointment, channel=channel).status


def inbound_message(customer, at):
    conversation, _ = Conversation.objects.get_or_create(customer=customer)
    message = Message.objects.create(
        conversation=conversation, direction=Message.Direction.IN, body="oi", wa_message_id="wamid.W1"
    )
    Message.objects.filter(pk=message.pk).update(created_at=at)


# ---------------------------------------------------------------- lembretes

def test_email_reminder_is_sent_when_due(appointment, whatsapp, mailoutbox):
    result = services.process_due_reminders(now=NOW_DUE)
    assert len(mailoutbox) == 1
    mail = mailoutbox[0]
    assert mail.to == ["cliente@example.com"]
    assert "Corte" in mail.body and "10:00" in mail.body and "Barbearia Teste" in mail.body
    assert channel_status(appointment, Reminder.Channel.EMAIL) == Reminder.Status.SENT
    assert result["sent"] >= 1


def test_nothing_is_sent_before_the_reminder_time(appointment, whatsapp, mailoutbox):
    result = services.process_due_reminders(now=NOW_EARLY)
    assert mailoutbox == []
    assert Reminder.objects.count() == 0
    assert result == {"sent": 0, "retry": 0, "failed": 0, "skipped": 0}


def test_running_twice_never_duplicates(appointment, whatsapp, mailoutbox):
    services.process_due_reminders(now=NOW_DUE)
    services.process_due_reminders(now=NOW_DUE)
    assert len(mailoutbox) == 1
    assert Reminder.objects.filter(appointment=appointment).count() == 2  # um por canal


def test_whatsapp_uses_the_template_when_configured(appointment, whatsapp, settings):
    settings.WHATSAPP_REMINDER_TEMPLATE = "lembrete_agendamento"
    services.process_due_reminders(now=NOW_DUE)
    assert whatsapp["text"] == []
    (call,) = whatsapp["template"]
    assert call["template"] == "lembrete_agendamento"
    assert call["language"] == "pt_BR"
    assert call["params"] == ["Corte", "07/01", "10:00", "Barbearia Teste"]
    assert channel_status(appointment, Reminder.Channel.WHATSAPP) == Reminder.Status.SENT


def test_whatsapp_free_text_inside_the_24h_window(appointment, whatsapp):
    inbound_message(appointment.customer, NOW_DUE - dt.timedelta(hours=1))
    services.process_due_reminders(now=NOW_DUE)
    (call,) = whatsapp["text"]
    assert "Corte" in call["body"] and "10:00" in call["body"]
    assert channel_status(appointment, Reminder.Channel.WHATSAPP) == Reminder.Status.SENT


def test_whatsapp_outside_window_without_template_fails_but_email_goes(appointment, whatsapp, mailoutbox):
    services.process_due_reminders(now=NOW_DUE)
    reminder = Reminder.objects.get(appointment=appointment, channel=Reminder.Channel.WHATSAPP)
    assert reminder.status == Reminder.Status.FAILED
    assert "janela" in reminder.last_error
    assert whatsapp["text"] == [] and whatsapp["template"] == []
    assert len(mailoutbox) == 1


def test_without_email_only_whatsapp_is_attempted(appointment, whatsapp, mailoutbox, settings):
    settings.WHATSAPP_REMINDER_TEMPLATE = "lembrete_agendamento"
    appointment.customer.email = ""
    appointment.customer.save()
    services.process_due_reminders(now=NOW_DUE)
    assert mailoutbox == []
    assert list(Reminder.objects.values_list("channel", flat=True)) == [Reminder.Channel.WHATSAPP]


def test_cancelled_appointment_gets_no_reminder(appointment, whatsapp, mailoutbox):
    appointment.status = Appointment.Status.CANCELLED
    appointment.save()
    services.process_due_reminders(now=NOW_DUE)
    assert mailoutbox == []
    assert Reminder.objects.count() == 0


def test_recently_booked_gets_no_reminder(appointment, whatsapp, mailoutbox):
    # Agendado depois do momento do lembrete (06/01 10:00): acabou de receber a confirmação.
    booked_at = dt.datetime(2030, 1, 6, 10, 30, tzinfo=TZ)
    Appointment.objects.filter(pk=appointment.pk).update(created_at=booked_at)
    services.process_due_reminders(now=NOW_DUE)
    assert mailoutbox == []
    assert Reminder.objects.count() == 0


def test_failures_are_retried_then_give_up_without_leaking_data(appointment, whatsapp, monkeypatch):
    def boom(*args, **kwargs):
        raise smtplib.SMTPRecipientsRefused({"cliente@example.com": (550, b"recusado")})

    monkeypatch.setattr(services, "send_mail", boom)
    for _ in range(4):
        services.process_due_reminders(now=NOW_DUE)
    reminder = Reminder.objects.get(appointment=appointment, channel=Reminder.Channel.EMAIL)
    assert reminder.status == Reminder.Status.FAILED
    assert reminder.attempts == services.MAX_ATTEMPTS  # a 4ª rodada não tentou de novo
    assert reminder.last_error == "SMTPRecipientsRefused"
    assert "cliente@example.com" not in reminder.last_error


def test_whatsapp_stays_pending_without_token(appointment, mailoutbox):
    # O token vazio vem do conftest (autouse): modo desenvolvimento.
    services.process_due_reminders(now=NOW_DUE)
    reminder = Reminder.objects.get(appointment=appointment, channel=Reminder.Channel.WHATSAPP)
    assert reminder.status == Reminder.Status.PENDING
    assert reminder.attempts == 0
    assert len(mailoutbox) == 1


def test_concurrent_run_cannot_claim_the_same_attempt(appointment, whatsapp, mailoutbox):
    reminder = Reminder.objects.create(appointment=appointment, channel=Reminder.Channel.EMAIL)
    Reminder.objects.filter(pk=reminder.pk).update(attempts=1)  # outra execução já reivindicou
    outcome = services._attempt(reminder, appointment, NOW_DUE)  # 'reminder' está desatualizado
    assert outcome == "skipped"
    assert mailoutbox == []


# ---------------------------------------------------------------- e-mail de confirmação

@pytest.fixture
def booking_setup(service, week_hours):
    """Serviço e semana aberta, para rodar o fluxo completo do bot."""


def book(say, email):
    for text in ("1", "1", "1", "1"):  # agendar, serviço, dia, horário
        say(text)
    say(email)
    return say("1")


def test_confirmation_email_is_sent_after_booking(say, booking_setup, mailoutbox):
    assert "Agendamento confirmado" in book(say, "cliente@example.com")
    assert len(mailoutbox) == 1
    mail = mailoutbox[0]
    assert mail.to == ["cliente@example.com"]
    assert "Agendamento confirmado" in mail.subject
    assert "Corte" in mail.body


def test_no_confirmation_email_when_customer_skips_email(say, booking_setup, mailoutbox):
    assert "Agendamento confirmado" in book(say, "pular")
    assert mailoutbox == []


def test_email_failure_never_breaks_the_booking(say, booking_setup, monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("smtp fora do ar")

    monkeypatch.setattr(services, "send_mail", boom)
    assert "Agendamento confirmado" in book(say, "cliente@example.com")
    assert Appointment.objects.count() == 1