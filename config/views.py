from django.http import JsonResponse
from django.views.decorators.http import require_safe


@require_safe
def health(request):
    """Sem banco de dados: responde rápido e serve para monitores e para 'acordar' o serviço."""
    return JsonResponse({"status": "ok"})