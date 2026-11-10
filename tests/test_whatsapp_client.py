from types import SimpleNamespace

import pytest

from apps.whatsapp import client


def test_without_token_nothing_is_sent(settings, monkeypatch):
    settings.WHATSAPP_ACCESS_TOKEN = ""

    def fail(*args, **kwargs):
        raise AssertionError("não deveria chamar a rede")

    monkeypatch.setattr(client.requests, "post", fail)
    assert client.send_text(phone_number_id="123", to="5535999990001", body="oi") is False


def test_send_text_builds_the_official_request(settings, monkeypatch):
    settings.WHATSAPP_ACCESS_TOKEN = "token-de-teste"
    settings.WHATSAPP_API_VERSION = "v99.0"
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured.update(url=url, json=json, headers=headers, timeout=timeout)
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(client.requests, "post", fake_post)
    assert client.send_text(phone_number_id="123", to="5535999990001", body="Olá") is True
    assert captured["url"] == "https://graph.facebook.com/v99.0/123/messages"
    assert captured["headers"]["Authorization"] == "Bearer token-de-teste"
    assert captured["json"]["to"] == "5535999990001"
    assert captured["json"]["type"] == "text"
    assert captured["json"]["text"]["body"] == "Olá"
    assert captured["timeout"]  # nunca sem limite de tempo


def test_api_error_raises_without_leaking_data(settings, monkeypatch):
    settings.WHATSAPP_ACCESS_TOKEN = "token-de-teste"
    response = SimpleNamespace(
        status_code=401, json=lambda: {"error": {"code": 190, "message": "token 5535999990001"}}
    )
    monkeypatch.setattr(client.requests, "post", lambda *args, **kwargs: response)
    with pytest.raises(client.WhatsAppSendError) as excinfo:
        client.send_text(phone_number_id="123", to="5535999990001", body="oi")
    assert "401" in str(excinfo.value)
    assert "5535999990001" not in str(excinfo.value)
def test_send_template_builds_the_official_request(settings, monkeypatch):
    settings.WHATSAPP_ACCESS_TOKEN = "token-de-teste"
    settings.WHATSAPP_API_VERSION = "v99.0"
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured.update(url=url, json=json)
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(client.requests, "post", fake_post)
    assert client.send_template(
        phone_number_id="123", to="5535999990001", template="lembrete", language="pt_BR", params=["Corte", "10:00"]
    ) is True
    assert captured["url"] == "https://graph.facebook.com/v99.0/123/messages"
    template = captured["json"]["template"]
    assert captured["json"]["type"] == "template"
    assert template["name"] == "lembrete"
    assert template["language"] == {"code": "pt_BR"}
    assert template["components"][0]["parameters"] == [
        {"type": "text", "text": "Corte"},
        {"type": "text", "text": "10:00"},
    ]


def test_send_template_without_token_sends_nothing(settings):
    settings.WHATSAPP_ACCESS_TOKEN = ""
    assert client.send_template(
        phone_number_id="123", to="5535999990001", template="lembrete", language="pt_BR", params=[]
    ) is False