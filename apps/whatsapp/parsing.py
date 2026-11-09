from dataclasses import dataclass

MAX_TEXT_LENGTH = 4096  # limite do WhatsApp para mensagens de texto


@dataclass(frozen=True)
class IncomingMessage:
    phone_number_id: str   # identifica o NEGÓCIO (o número que recebeu a mensagem)
    wa_id: str             # telefone do cliente
    wa_message_id: str     # id único da mensagem na Meta
    text: str
    profile_name: str = ""


def _dicts(value):
    """Devolve só os itens dict de uma lista (ignora qualquer outra coisa)."""
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def parse_incoming_messages(payload) -> list[IncomingMessage]:
    if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
        return []

    result = []
    for entry in _dicts(payload.get("entry")):
        for change in _dicts(entry.get("changes")):
            if change.get("field") != "messages":
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue

            metadata = value.get("metadata")
            phone_number_id = str(metadata.get("phone_number_id", "")) if isinstance(metadata, dict) else ""

            names = {}
            for contact in _dicts(value.get("contacts")):
                profile = contact.get("profile")
                if isinstance(profile, dict):
                    names[str(contact.get("wa_id", ""))] = str(profile.get("name", ""))[:120]

            # Atualizações de entrega/leitura vêm em "statuses" e são ignoradas.
            for message in _dicts(value.get("messages")):
                if message.get("type") != "text":
                    continue  # MVP: só texto
                text_obj = message.get("text")
                body = text_obj.get("body") if isinstance(text_obj, dict) else None
                wa_id = str(message.get("from", ""))
                message_id = str(message.get("id", ""))
                if not (phone_number_id and wa_id and message_id and isinstance(body, str) and body.strip()):
                    continue
                result.append(
                    IncomingMessage(
                        phone_number_id=phone_number_id,
                        wa_id=wa_id,
                        wa_message_id=message_id,
                        text=body[:MAX_TEXT_LENGTH],
                        profile_name=names.get(wa_id, ""),
                    )
                )
    return result