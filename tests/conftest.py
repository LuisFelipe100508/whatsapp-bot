import datetime as dt
import itertools

import pytest
from django.contrib.auth import get_user_model

from apps.businesses.models import Business, BusinessHours, Service
from apps.customers.models import Customer
from apps.whatsapp import client
from apps.whatsapp.parsing import IncomingMessage
from apps.whatsapp.services import ingest_message


@pytest.fixture(autouse=True)
def no_real_whatsapp_calls(settings):
    """Token vazio em todos os testes: nenhum teste chega a falar com a Meta."""
    settings.WHATSAPP_ACCESS_TOKEN = ""


@pytest.fixture
def business(db):
    owner = get_user_model().objects.create_user(username="dono")
    biz = Business.objects.create(
        owner=owner, name="Barbearia Teste", whatsapp_phone_number_id="123456"
    )
    # Segunda-feira, 09:00 às 12:00
    BusinessHours.objects.create(
        business=biz, weekday=0, opens_at=dt.time(9, 0), closes_at=dt.time(12, 0)
    )
    return biz


@pytest.fixture
def service(business):
    return Service.objects.create(
        business=business, name="Corte", price="40.00", duration_minutes=30
    )


@pytest.fixture
def customer(business):
    return Customer.objects.create(
        business=business, phone="5535999999999", name="Cliente Teste"
    )


@pytest.fixture
def week_hours(business):
    """Terça a domingo, 09:00-18:00 (a segunda já vem da fixture 'business')."""
    for weekday in range(1, 7):
        BusinessHours.objects.create(
            business=business, weekday=weekday, opens_at=dt.time(9, 0), closes_at=dt.time(18, 0)
        )


@pytest.fixture
def sent(monkeypatch):
    """Captura o texto de cada resposta que o bot 'enviaria' ao WhatsApp."""
    box = []

    def fake_send(*, phone_number_id, to, body):
        box.append(body)
        return True

    monkeypatch.setattr(client, "send_text", fake_send)
    return box


@pytest.fixture
def say(sent, business):
    """Simula o cliente mandando uma mensagem; devolve a última resposta do bot."""
    counter = itertools.count(1)

    def _say(text, wa_id="5535999990001"):
        ingest_message(
            IncomingMessage(
                phone_number_id="123456",
                wa_id=wa_id,
                wa_message_id=f"wamid.T{next(counter)}",
                text=text,
                profile_name="Cliente Teste",
            )
        )
        return sent[-1]

    return _say