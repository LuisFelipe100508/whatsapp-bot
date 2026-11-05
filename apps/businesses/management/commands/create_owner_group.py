from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from apps.bot.models import BotReply
from apps.businesses.models import Business, BusinessHours, Service
from apps.conversations.models import Conversation, Message
from apps.customers.models import Customer
from apps.notifications.models import Reminder
from apps.scheduling.models import Appointment

OWNER_GROUP = "Donos de negócio"

# Princípio do menor privilégio: só o que o dono realmente precisa.
PERMISSIONS = {
    Business: ["view", "change"],
    Service: ["view", "add", "change"],
    BusinessHours: ["view", "add", "change", "delete"],
    BotReply: ["view", "add", "change"],
    Customer: ["view"],
    Conversation: ["view"],
    Message: ["view"],
    Appointment: ["view", "change"],
    Reminder: ["view"],
}


class Command(BaseCommand):
    help = "Cria/atualiza o grupo de permissões dos donos de negócio (idempotente)."

    def handle(self, *args, **options):
        group, _ = Group.objects.get_or_create(name=OWNER_GROUP)
        perms = []
        for model, actions in PERMISSIONS.items():
            content_type = ContentType.objects.get_for_model(model)
            for action in actions:
                codename = f"{action}_{model._meta.model_name}"
                perms.append(Permission.objects.get(content_type=content_type, codename=codename))
        group.permissions.set(perms)  # substitui: remove permissões que sobraram
        self.stdout.write(self.style.SUCCESS(f"Grupo '{OWNER_GROUP}' atualizado ({len(perms)} permissões)."))