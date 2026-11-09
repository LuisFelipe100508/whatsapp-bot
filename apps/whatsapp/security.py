import hashlib
import hmac

from django.conf import settings

SIGNATURE_PREFIX = "sha256="


def is_valid_verify_token(token: str) -> bool:
    expected = settings.WHATSAPP_VERIFY_TOKEN
    if not expected or not token:  # falha segura: token vazio nunca é aceito
        return False
    return hmac.compare_digest(token.encode(), expected.encode())


def is_valid_signature(body: bytes, header: str) -> bool:
    """Valida o header X-Hub-Signature-256 contra o corpo BRUTO da requisição."""
    secret = settings.WHATSAPP_APP_SECRET
    if not secret or not header.startswith(SIGNATURE_PREFIX):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    provided = header[len(SIGNATURE_PREFIX):]
    # Tempo constante: não revela, pelo tempo de resposta, quantos caracteres acertou.
    return hmac.compare_digest(expected.encode(), provided.encode())