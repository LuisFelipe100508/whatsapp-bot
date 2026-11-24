"""Registro seguro dos eventos de status de entrega enviados pela Meta.

LGPD: so registramos status, codigo e titulo do erro. Nunca registramos
telefone, ids de contato nem o id da mensagem (o wamid embute o numero).
"""
import logging

logger = logging.getLogger(__name__)

_MAX_TITLE = 120


def _safe_text(value, limit=_MAX_TITLE):
    """Texto curto, em uma linha, ou '?' se nao for string."""
    if not isinstance(value, str):
        return "?"
    return " ".join(value.split())[:limit]


def _safe_code(value):
    """Codigo de erro numerico, ou '?' se vier algo inesperado."""
    return value if isinstance(value, int) and not isinstance(value, bool) else "?"


def log_delivery_statuses(payload):
    """Registra falhas de entrega (status 'failed') e devolve quantas houve.

    Nunca levanta excecao: um payload estranho nao pode derrubar o webhook.
    """
    total = failed = 0
    try:
        for entry in payload.get("entry") or []:
            for change in entry.get("changes") or []:
                value = change.get("value") or {}
                for item in value.get("statuses") or []:
                    total += 1
                    if item.get("status") != "failed":
                        continue
                    failed += 1
                    for err in item.get("errors") or [{}]:
                        logger.warning(
                            "webhook: entrega falhou (codigo=%s, titulo=%s)",
                            _safe_code(err.get("code")),
                            _safe_text(err.get("title")),
                        )
    except (AttributeError, TypeError) as exc:
        # So o NOME da classe: a mensagem do erro pode conter dados pessoais.
        logger.error("webhook: payload de status inesperado (%s)", type(exc).__name__)
        return failed

    if total:
        logger.info("webhook: status recebidos=%d falhas_entrega=%d", total, failed)
    return failed