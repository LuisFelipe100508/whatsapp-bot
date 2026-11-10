import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from django.core.management.base import BaseCommand
from django.db import close_old_connections

from apps.notifications.services import process_due_reminders

logger = logging.getLogger(__name__)


def run_job():
    close_old_connections()
    try:
        process_due_reminders()
    except Exception as exc:  # noqa: BLE001
        logger.error("scheduler: falha na execucao (%s)", type(exc).__name__)  # o agendador segue vivo
    finally:
        close_old_connections()


class Command(BaseCommand):
    help = "Roda o APScheduler enviando lembretes a cada N minutos (uso local; Ctrl+C para parar)."

    def add_arguments(self, parser):
        parser.add_argument("--minutes", type=int, default=5)

    def handle(self, *args, **options):
        scheduler = BlockingScheduler()
        # max_instances=1 e coalesce: execuções atrasadas não se acumulam nem rodam em paralelo.
        scheduler.add_job(run_job, "interval", minutes=options["minutes"], max_instances=1, coalesce=True)
        self.stdout.write(f"Agendador ativo (a cada {options['minutes']} min). Ctrl+C para parar.")
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self.stdout.write("Agendador encerrado.")