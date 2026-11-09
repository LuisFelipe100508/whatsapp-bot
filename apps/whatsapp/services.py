import logging
import re

from django.db import transaction

from apps.bot.engine import handle_message
from apps.businesses.models import Business
from apps.conversations.models import Conversation, Message
from apps.customers.models import Customer

from .parsing import IncomingMessage

logger = logging.getLogger(__name__)
PHONE_RE = re.compile(r"\d{8,15}")


def ingest_message(incoming: IncomingMessage) -> bool:
    """Grava a mensagem e chama o bot. Devolve False se ignorada ou duplicada."""
    business = Business.objects.filter(
        whatsapp_phone_number_id=incoming.phone_number_id, is_active=True
    ).first()
    if business is None:
        logger.warning("webhook: mensagem para negocio desconhecido ou inativo")
        return False
    if not PHONE_RE.fullmatch(incoming.wa_id):
        logger.warning("webhook: identificador de cliente invalido")
        return False

    with transaction.atomic():
        customer, _ = Customer.objects.get_or_create(
            business=business, phone=incoming.wa_id, defaults={"name": incoming.profile_name}
        )
        conversation, _ = Conversation.objects.get_or_create(customer=customer)
        # get_or_create + unique no banco = idempotência mesmo com entregas simultâneas.
        message, created = Message.objects.get_or_create(
            wa_message_id=incoming.wa_message_id,
            defaults={
                "conversation": conversation,
                "direction": Message.Direction.IN,
                "body": incoming.text,
            },
        )

    if not created:
        logger.info("webhook: mensagem duplicada ignorada")
        return False

    handle_message(message)  # fora da transação: a mensagem já está salva
    return True