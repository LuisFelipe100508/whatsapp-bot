"""Simula a Meta enviando uma mensagem ao servidor local (demo e testes manuais).

Uso: python scripts/simulate_webhook.py "Oi" [phone_number_id]
"""
import hashlib
import hmac
import json
import os
import sys

import environ
import requests

environ.Env.read_env(".env")  # lê o mesmo .env do servidor, então o App Secret bate

text = sys.argv[1] if len(sys.argv) > 1 else "Oi"
phone_number_id = sys.argv[2] if len(sys.argv) > 2 else "TESTE-123"
url = os.environ.get("WEBHOOK_URL", "http://127.0.0.1:8000/webhook/whatsapp/")

payload = {
    "object": "whatsapp_business_account",
    "entry": [{"id": "WABA-DEMO", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp",
        "metadata": {"display_phone_number": "15550001111", "phone_number_id": phone_number_id},
        "contacts": [{"profile": {"name": "Cliente Demo"}, "wa_id": "5535999990001"}],
        "messages": [{
            "from": "5535999990001",
            "id": f"wamid.DEMO{os.urandom(4).hex()}",
            "timestamp": "1730000000",
            "type": "text",
            "text": {"body": text},
        }],
    }}]}],
}

body = json.dumps(payload).encode()
signature = "sha256=" + hmac.new(os.environ["WHATSAPP_APP_SECRET"].encode(), body, hashlib.sha256).hexdigest()
response = requests.post(url, data=body, headers={"Content-Type": "application/json", "X-Hub-Signature-256": signature}, timeout=10)
print(response.status_code, response.text)