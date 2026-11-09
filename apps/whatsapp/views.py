import json
import logging

from django.http import HttpResponse
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .parsing import parse_incoming_messages
from .security import is_valid_signature, is_valid_verify_token
from .services import ingest_message

logger = logging.getLogger(__name__)


class WhatsAppWebhookView(APIView):
    # A autenticação aqui é a ASSINATURA HMAC, não sessão nem token de usuário.
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "webhook"  # taxa definida em REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]

    def get(self, request):
        """Verificação inicial: a Meta confirma que o endpoint é nosso."""
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token", "")
        challenge = request.query_params.get("hub.challenge", "")
        if mode == "subscribe" and challenge and is_valid_verify_token(token):
            return HttpResponse(challenge[:128], content_type="text/plain")
        logger.warning("webhook: verificacao recusada")
        return Response({"detail": "forbidden"}, status=403)

    def post(self, request):
        body = request.body  # bytes brutos: precisam ser lidos ANTES de qualquer parse
        if not is_valid_signature(body, request.headers.get("X-Hub-Signature-256", "")):
            logger.warning("webhook: assinatura invalida")
            return Response({"detail": "forbidden"}, status=403)

        try:
            payload = json.loads(body)
        except ValueError:
            return Response({"detail": "invalid json"}, status=400)

        messages = parse_incoming_messages(payload)
        new = failed = 0
        for incoming in messages:
            try:
                new += ingest_message(incoming)
            except Exception as exc:  # noqa: BLE001
                # Só o NOME da classe: a mensagem do erro pode conter dados pessoais.
                failed += 1
                logger.error("webhook: falha ao processar mensagem (%s)", type(exc).__name__)

        logger.info("webhook: recebidas=%d novas=%d falhas=%d", len(messages), new, failed)
        return Response({"status": "ok"})