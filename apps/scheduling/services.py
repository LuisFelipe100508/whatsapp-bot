import datetime as dt
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Appointment

LOCAL_TZ = ZoneInfo(settings.TIME_ZONE)
SLOT_STEP = dt.timedelta(minutes=30)
MIN_NOTICE = dt.timedelta(minutes=60)
MAX_DAYS_AHEAD = 30
EXCLUSION_CONSTRAINT = "no_overlapping_confirmed_appointments"


class SchedulingError(Exception):
    """Base dos erros de agendamento."""


class SlotUnavailable(SchedulingError):
    """O horário não está livre (ou não existe)."""


class InvalidRequest(SchedulingError):
    """Dados inconsistentes (ex.: serviço de outro negócio)."""


def has_conflict(business_id, start_at, end_at, exclude_pk=None):
    """True se existe agendamento confirmado sobrepondo [start_at, end_at)."""
    qs = Appointment.objects.filter(
        business_id=business_id,
        status=Appointment.Status.CONFIRMED,
        start_at__lt=end_at,
        end_at__gt=start_at,
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()


def get_available_slots(business, service, day, now=None):
    """Horários de início livres em `day` (date local), em ordem crescente."""
    now = now or timezone.now()
    if not business.is_active or not service.is_active or service.business_id != business.pk:
        return []

    today = now.astimezone(LOCAL_TZ).date()
    if day < today or day > today + dt.timedelta(days=MAX_DAYS_AHEAD):
        return []

    hours = business.hours.filter(weekday=day.weekday()).first()
    if hours is None:  # sem registro = fechado nesse dia
        return []

    opens = dt.datetime.combine(day, hours.opens_at, tzinfo=LOCAL_TZ)
    closes = dt.datetime.combine(day, hours.closes_at, tzinfo=LOCAL_TZ)
    duration = dt.timedelta(minutes=service.duration_minutes)

    busy = list(
        Appointment.objects.filter(
            business=business,
            status=Appointment.Status.CONFIRMED,
            start_at__lt=closes,
            end_at__gt=opens,
        ).values_list("start_at", "end_at")
    )

    earliest = now + MIN_NOTICE
    slots = []
    slot = opens
    while slot + duration <= closes:
        end = slot + duration
        is_free = not any(slot < b_end and end > b_start for b_start, b_end in busy)
        if slot >= earliest and is_free:
            slots.append(slot)
        slot += SLOT_STEP
    return slots


def create_appointment(*, business, customer, service, start_at, now=None):
    """Cria o agendamento ou levanta SchedulingError. Seguro contra concorrência."""
    if timezone.is_naive(start_at):
        raise InvalidRequest("O horário precisa ter fuso (datetime aware).")
    if service.business_id != business.pk or customer.business_id != business.pk:
        raise InvalidRequest("Serviço ou cliente não pertence a este negócio.")

    local_day = start_at.astimezone(LOCAL_TZ).date()
    # Pré-checagem: valida expediente, grade, antecedência e conflito.
    if start_at not in get_available_slots(business, service, local_day, now=now):
        raise SlotUnavailable("Horário indisponível.")

    try:
        with transaction.atomic():
            return Appointment.objects.create(
                business=business,
                customer=customer,
                service=service,
                start_at=start_at,
                end_at=start_at + dt.timedelta(minutes=service.duration_minutes),
            )
    except IntegrityError as exc:
        # Duas pessoas pegaram o mesmo horário ao mesmo tempo: o banco barrou a segunda.
        constraint = getattr(getattr(exc.__cause__, "diag", None), "constraint_name", None)
        if constraint == EXCLUSION_CONSTRAINT:
            raise SlotUnavailable("Horário acabou de ser ocupado.") from exc
        raise


def cancel_appointment(appointment):
    if appointment.status != Appointment.Status.CONFIRMED:
        raise InvalidRequest("Só agendamentos confirmados podem ser cancelados.")
    appointment.status = Appointment.Status.CANCELLED
    appointment.save(update_fields=["status", "updated_at"])
    return appointment