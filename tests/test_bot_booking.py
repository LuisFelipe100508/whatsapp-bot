import datetime as dt

import pytest
from django.utils import timezone

from apps.conversations.models import Conversation, Message
from apps.customers.models import Customer
from apps.scheduling import services as scheduling
from apps.scheduling.models import Appointment
from apps.scheduling.services import LOCAL_TZ
from apps.whatsapp import client
from apps.whatsapp.parsing import IncomingMessage
from apps.whatsapp.services import ingest_message

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def booking_setup(service, week_hours):
    """Todo teste aqui tem um serviço e o negócio aberto a semana toda."""


def reach_email_prompt(say):
    for text in ("1", "1", "1", "1"):  # agendar, serviço, dia, horário
        reply = say(text)
    return reply


def test_full_booking_flow(say, service):
    assert "Qual serviço" in say("1")
    assert "Para qual dia" in say("1")
    assert "Horários livres" in say("1")
    assert "e-mail" in say("1")
    assert "Confirme seu agendamento" in say("cliente@example.com")
    assert "Agendamento confirmado" in say("1")

    appointment = Appointment.objects.get()
    assert appointment.status == Appointment.Status.CONFIRMED
    assert appointment.service == service
    customer = Customer.objects.get()
    assert customer.email == "cliente@example.com"
    assert customer.consent_at is not None
    conversation = Conversation.objects.get()
    assert conversation.state == Conversation.State.IDLE
    assert conversation.context == {}
    assert Message.objects.filter(direction=Message.Direction.OUT).count() == 6


def test_known_email_skips_the_email_question(say):
    say("oi")
    Customer.objects.update(email="ja@example.com")
    for text in ("1", "1", "1"):
        say(text)
    assert "Confirme seu agendamento" in say("1")


def test_email_is_optional(say):
    reach_email_prompt(say)
    assert "Confirme seu agendamento" in say("pular")
    say("1")
    customer = Customer.objects.get()
    assert customer.email == ""
    assert customer.consent_at is None
    assert Appointment.objects.count() == 1


def test_invalid_email_asks_again(say):
    reach_email_prompt(say)
    assert "E-mail inválido" in say("isso nao e um email")
    assert Conversation.objects.get().state == Conversation.State.ASKING_EMAIL


def test_invalid_option_repeats_the_question(say):
    say("1")
    reply = say("9")
    assert "Opção inválida" in reply
    assert "Qual serviço" in reply
    assert Conversation.objects.get().state == Conversation.State.CHOOSING_SERVICE


def test_zero_returns_to_menu_mid_flow(say):
    say("1")
    assert "*1* - Agendar horário" in say("0")
    assert Conversation.objects.get().state == Conversation.State.IDLE


def test_slot_taken_before_confirmation(say, business, service):
    for text in ("1", "1", "2", "1"):  # dia 2 da lista: sempre um dia inteiro livre
        say(text)
    say("cliente@example.com")
    start = dt.datetime.fromisoformat(Conversation.objects.get().context["start"])

    other = Customer.objects.create(business=business, phone="5535988887777")
    scheduling.create_appointment(business=business, customer=other, service=service, start_at=start)

    reply = say("1")
    assert "indisponível" in reply
    assert Appointment.objects.count() == 1  # só o da outra pessoa
    assert Conversation.objects.get().state == Conversation.State.CHOOSING_TIME


def test_time_can_be_typed(say):
    for text in ("1", "1", "2"):
        say(text)
    slots = Conversation.objects.get().context["slots"]
    typed = dt.datetime.fromisoformat(slots[2]).astimezone(LOCAL_TZ).strftime("%H:%M")
    say(typed)
    conversation = Conversation.objects.get()
    assert conversation.state == Conversation.State.ASKING_EMAIL
    assert conversation.context["start"] == slots[2]


def test_date_can_be_typed(say):
    for text in ("1", "1"):
        say(text)
    dates = Conversation.objects.get().context["dates"]
    day = dt.date.fromisoformat(dates[1])
    say(f"{day.day:02d}/{day.month:02d}")
    conversation = Conversation.objects.get()
    assert conversation.state == Conversation.State.CHOOSING_TIME
    assert conversation.context["date"] == dates[1]


def test_no_active_services(say, service):
    service.is_active = False
    service.save()
    assert "não há serviços" in say("1")


def test_customer_cannot_exceed_active_appointment_limit(say, business, service):
    say("oi")
    customer = Customer.objects.get()
    base = timezone.now() + dt.timedelta(days=2)
    for i in range(3):
        start = base + dt.timedelta(days=i)
        Appointment.objects.create(
            business=business, customer=customer, service=service,
            start_at=start, end_at=start + dt.timedelta(minutes=30),
        )
    assert "limite" in say("1")
    assert Conversation.objects.get().state == Conversation.State.IDLE


def test_corrupted_context_restarts_the_conversation(say):
    say("oi")
    Conversation.objects.update(state=Conversation.State.CHOOSING_TIME, context={})
    assert "*1* - Agendar horário" in say("1")
    assert Conversation.objects.get().state == Conversation.State.IDLE


def test_send_failure_does_not_break_processing(business, monkeypatch, caplog):
    def boom(**kwargs):
        raise client.WhatsAppSendError("HTTP 500")

    monkeypatch.setattr(client, "send_text", boom)
    incoming = IncomingMessage(
        phone_number_id="123456", wa_id="5535999990001", wa_message_id="wamid.F1", text="Oi"
    )
    assert ingest_message(incoming) is True
    assert Message.objects.filter(direction=Message.Direction.OUT).count() == 1
    assert "5535999990001" not in caplog.text