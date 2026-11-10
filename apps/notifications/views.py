import logging

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .security import is_valid_cron_token
from .services import process_due_reminders

logger = logging.getLogger(__name__)


class SendRemindersView(APIView):
    """Chamado por um cron externo. A autenticação é o token, não sessão de usuário."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "cron"

    def post(self, request):
        if not is_valid_cron_token(request.headers.get("Authorization", "")):
            logger.warning("cron: token invalido")
            return Response({"detail": "forbidden"}, status=403)
        return Response(process_due_reminders())  # só contagens, nunca dados pessoais