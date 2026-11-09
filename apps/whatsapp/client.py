import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/{version}/{phone_number_id}/messages"
TIMEOUT = (3.05, 10)  # (conectar, ler): nunca esperar para sempre


class WhatsAppSendError(Exception):
    """Falha ao enviar. A mensagem nunca contém telefone nem texto."""


def _error_code(response) -> str:
    try:
        code = response.json().get("error", {}).get("code")
    except (ValueError, AttributeError):
        return ""
    return f", codigo {code}" if isinstance(code, int) else ""


def send_text(*, phone_number_id: str, to: str, body: str) -> bool:
    """Envia texto pela Cloud API oficial.

    True = enviado. False = token não configurado (nada foi enviado).
    Levanta WhatsAppSendError se a Meta ou a rede falharem.
    """
    token = settings.WHATSAPP_ACCESS_TOKEN
    if not token:
        logger.warning("whatsapp: token nao configurado; mensagem nao enviada")
        return False

    url = GRAPH_URL.format(version=settings.WHATSAPP_API_VERSION, phone_number_id=phone_number_id)
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body, "preview_url": False},
    }
    try:
        response = requests.post(
            url, json=payload, headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT
        )
    except requests.RequestException as exc:
        raise WhatsAppSendError(type(exc).__name__) from None  # sem encadear a exceção original
    if response.status_code >= 400:
        raise WhatsAppSendError(f"HTTP {response.status_code}{_error_code(response)}")
    return True