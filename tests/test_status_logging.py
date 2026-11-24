import logging

from apps.whatsapp.statuses import log_delivery_statuses


def _payload(statuses):
    return {"entry": [{"changes": [{"value": {"statuses": statuses}}]}]}


def test_falha_e_registrada_sem_dados_pessoais(caplog):
    payload = _payload([{
        "id": "wamid.SEGREDO123",
        "status": "failed",
        "recipient_id": "5500000000000",
        "errors": [{
            "code": 130497,
            "title": "Business account is restricted from messaging users in this country.",
        }],
    }])
    with caplog.at_level(logging.INFO, logger="apps.whatsapp.statuses"):
        assert log_delivery_statuses(payload) == 1

    assert "130497" in caplog.text
    assert "restricted" in caplog.text
    assert "wamid" not in caplog.text
    assert "SEGREDO123" not in caplog.text
    assert "5500000000000" not in caplog.text


def test_entrega_bem_sucedida_nao_conta_como_falha():
    payload = _payload([{"id": "wamid.X", "status": "delivered"}])
    assert log_delivery_statuses(payload) == 0


def test_payload_malformado_nao_levanta_excecao():
    assert log_delivery_statuses({"entry": "lixo"}) == 0
    assert log_delivery_statuses(None) == 0