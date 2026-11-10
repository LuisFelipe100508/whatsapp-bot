import hmac

from django.conf import settings

MIN_TOKEN_LENGTH = 32


def is_valid_cron_token(authorization: str) -> bool:
    """Espera o header 'Authorization: Bearer <token>'."""
    expected = settings.REMINDER_CRON_TOKEN
    if len(expected) < MIN_TOKEN_LENGTH:  # falha segura: token vazio ou fraco nunca vale
        return False
    scheme, _, provided = authorization.partition(" ")
    if scheme.lower() != "bearer" or not provided.strip():
        return False
    return hmac.compare_digest(provided.strip().encode(), expected.encode())