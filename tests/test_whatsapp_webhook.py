import hashlib
import hmac
import json
import logging

import pytest
from django.core.cache import cache
from rest_framework.throttling import ScopedRateThrottle

from apps.conversations.models import Conversation, Message
from apps.customers.models import Customer

URL = "/webhook/whatsapp/"
APP_SECRET = "test-app-secret"
VERIFY_TOKEN = "test-verify-token"
NO_HEADER = object()

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def meta_settings(settings):
    settings.WHATSAPP_APP_SECRET = APP_SECRET
    settings.WHATSAPP_VERIFY_TOKEN = VERIFY_TOKEN
    cache.clear()  # zera os contadores do rate limit entre os testes


def sign(body: bytes, secret: str = APP_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def make_payload(
    text="Oi", msg_id="wamid.AAA", wa_id="5535999990001", phone_number_id="123456", msg_type="text"
):
    message = {"from": wa_id, "id": msg_id, "timestamp": "1730000000", "type": msg_type}
    if msg_type == "text":
        message["text"] = {"body": text}
    else:
        message[msg_type] = {"id": "media-1"}
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "WABA-1",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "15550001111", "phone_number_id": phone_number_id},
                    "contacts": [{"profile": {"name": "Cliente Teste"}, "wa_id": wa_id}],
                    "messages": [message],
                },
            }],
        }],
    }


def post(client, data, *, signature=None, secret=APP_SECRET, raw=None):
    """signature=None assina corretamente; NO_HEADER omite o header; outro valor é enviado como está."""
    body = raw if raw is not None else json.dumps(data).encode()
    extra = {}
    if signature is None:
        extra["HTTP_X_HUB_SIGNATURE_256"] = sign(body, secret)
    elif signature is not NO_HEADER:
        extra["HTTP_X_HUB_SIGNATURE_256"] = signature
    return client.post(URL, data=body, content_type="application/json", **extra)


# ---------- GET: verificação do webhook ----------

def test_verification_returns_challenge(client):
    response = client.get(URL, {"hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "1158201444"})
    assert response.status_code == 200
    assert response.content == b"1158201444"


def test_verification_rejects_wrong_token(client):
    response = client.get(URL, {"hub.mode": "subscribe", "hub.verify_token": "errado", "hub.challenge": "123"})
    assert response.status_code == 403


def test_verification_fails_closed_when_token_not_configured(client, settings):
    settings.WHATSAPP_VERIFY_TOKEN = ""
    response = client.get(URL, {"hub.mode": "subscribe", "hub.verify_token": "", "hub.challenge": "123"})
    assert response.status_code == 403


# ---------- POST: assinatura ----------

def test_valid_signature_stores_message(client, business):
    response = post(client, make_payload(text="Oi"))
    assert response.status_code == 200
    message = Message.objects.get()
    assert message.body == "Oi"
    assert message.direction == Message.Direction.IN
    assert Customer.objects.filter(business=business, phone="5535999990001").exists()
    assert Conversation.objects.count() == 1


def test_invalid_signature_is_rejected(client, business):
    response = post(client, make_payload(), signature="sha256=" + "0" * 64)
    assert response.status_code == 403
    assert Message.objects.count() == 0


def test_missing_signature_is_rejected(client, business):
    response = post(client, make_payload(), signature=NO_HEADER)
    assert response.status_code == 403
    assert Message.objects.count() == 0


def test_tampered_body_is_rejected(client, business):
    signed = sign(json.dumps(make_payload(text="original")).encode())
    response = post(client, make_payload(text="adulterada"), signature=signed)
    assert response.status_code == 403
    assert Message.objects.count() == 0


def test_signature_check_fails_closed_without_app_secret(client, business, settings):
    settings.WHATSAPP_APP_SECRET = ""
    response = post(client, make_payload(), secret="")  # assinado com segredo vazio
    assert response.status_code == 403
    assert Message.objects.count() == 0


# ---------- POST: comportamento ----------

def test_duplicate_delivery_is_processed_once(client, business, monkeypatch):
    calls = []
    monkeypatch.setattr("apps.whatsapp.services.handle_message", lambda message: calls.append(message.pk))
    assert post(client, make_payload(msg_id="wamid.DUP")).status_code == 200
    assert post(client, make_payload(msg_id="wamid.DUP")).status_code == 200
    assert Message.objects.count() == 1
    assert len(calls) == 1


def test_unknown_business_is_ignored_with_200(client, business):
    response = post(client, make_payload(phone_number_id="999999"))
    assert response.status_code == 200
    assert Message.objects.count() == 0


def test_status_updates_are_ignored(client, business):
    statuses = {
        "object": "whatsapp_business_account",
        "entry": [{"id": "1", "changes": [{"field": "messages", "value": {
            "messaging_product": "whatsapp",
            "metadata": {"phone_number_id": "123456"},
            "statuses": [{"id": "wamid.X", "status": "delivered"}],
        }}]}],
    }
    assert post(client, statuses).status_code == 200
    assert Message.objects.count() == 0


def test_non_text_messages_are_ignored(client, business):
    assert post(client, make_payload(msg_type="image")).status_code == 200
    assert Message.objects.count() == 0


def test_invalid_json_with_valid_signature_returns_400(client, business):
    assert post(client, None, raw=b"{isso nao e json").status_code == 400


# ---------- Rate limit e LGPD ----------

def test_rate_limit_returns_429(client, business, monkeypatch):
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "webhook", "3/min")
    codes = [post(client, make_payload(msg_id=f"wamid.{i}")).status_code for i in range(5)]
    assert codes == [200, 200, 200, 429, 429]


def test_logs_never_contain_personal_data(client, business, caplog):
    caplog.set_level(logging.INFO)
    post(client, make_payload(text="Mensagem secreta do cliente", wa_id="5535999990001"))
    post(client, make_payload(text="x"), signature="sha256=" + "0" * 64)  # também o caminho de erro
    assert caplog.text  # garante que algo foi logado
    for sensitive in ("5535999990001", "Mensagem secreta", "Cliente Teste"):
        assert sensitive not in caplog.text