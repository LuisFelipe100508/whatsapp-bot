from django.core.management.base import BaseCommand

from apps.notifications.services import process_due_reminders


class Command(BaseCommand):
    help = "Envia os lembretes vencidos (idempotente: pode rodar quantas vezes quiser)."

    def handle(self, *args, **options):
        r = process_due_reminders()
        self.stdout.write(
            f"Lembretes: enviados={r['sent']} nova_tentativa={r['retry']} "
            f"falhas={r['failed']} ignorados={r['skipped']}"
        )