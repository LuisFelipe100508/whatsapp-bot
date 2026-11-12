"""Chat de demonstração no terminal: conversa com o bot sem precisar da Meta.

Usa o banco do .env (desenvolvimento) e mostra as respostas do bot na tela.
Pré-requisito: um negócio com 'ID do número no WhatsApp' = TESTE-123, com
serviços e horários cadastrados (veja o README).

Uso: python scripts/chat_demo.py [phone_number_id] [telefone]
Digite 'sair' para encerrar.
"""
import logging
import os
import random
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.dev"
# Na demo, e-mails só aparecem no terminal: nunca são enviados de verdade.
os.environ["EMAIL_BACKEND"] = "django.core.mail.backends.console.EmailBackend"

import django  # noqa: E402

django.setup()

from apps.whatsapp import client  # noqa: E402
from apps.whatsapp.parsing import IncomingMessage  # noqa: E402
from apps.whatsapp.services import ingest_message  # noqa: E402

logging.getLogger("apps").setLevel(logging.WARNING)  # sem logs técnicos na tela da demo
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def fake_send(*, phone_number_id, to, body):
    print("\n🤖 Bot:")
    print("\n".join("   " + line for line in body.splitlines()))
    return True


client.send_text = fake_send  # nada é enviado ao WhatsApp de verdade

phone_number_id = sys.argv[1] if len(sys.argv) > 1 else "TESTE-123"
# Telefone fictício novo a cada execução (o bot limita 3 agendamentos ativos por cliente).
wa_id = sys.argv[2] if len(sys.argv) > 2 else "5511" + str(random.randint(900000000, 999999999))

print("Chat de demonstração. Digite 'sair' para encerrar.")
while True:
    try:
        text = input("\n👤 Você: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        break
    if text.lower() in {"sair", "exit"}:
        break
    if not text:
        continue
    delivered = ingest_message(
        IncomingMessage(
            phone_number_id=phone_number_id,
            wa_id=wa_id,
            wa_message_id=f"wamid.DEMO{uuid.uuid4().hex}",
            text=text,
            profile_name="Cliente Demo",
        )
    )
    if not delivered:
        print("\n⚠️  Negócio não encontrado: cadastre um com ID de número TESTE-123 no admin.")