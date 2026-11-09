from django.core.management.base import BaseCommand

from apps.bot.models import BotReply
from apps.bot.replies import DEFAULTS
from apps.businesses.models import Business


class Command(BaseCommand):
    help = "Cria as respostas padrão do bot (idempotente: nunca sobrescreve o que o dono editou)."

    def add_arguments(self, parser):
        parser.add_argument("--business", type=int, help="ID de um negócio (padrão: todos)")

    def handle(self, *args, **options):
        businesses = Business.objects.all()
        if options["business"]:
            businesses = businesses.filter(pk=options["business"])
        created = 0
        for business in businesses:
            for intent, default in DEFAULTS.items():
                _, was_created = BotReply.objects.get_or_create(
                    business=business,
                    intent=intent,
                    defaults={"keywords": default["keywords"], "text": default["text"]},
                )
                created += was_created
        self.stdout.write(self.style.SUCCESS(f"{created} resposta(s) criada(s)."))