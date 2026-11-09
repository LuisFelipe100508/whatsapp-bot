import datetime as dt
import logging
import re

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from apps.businesses.models import Service
from apps.conversations.models import Conversation, Message
from apps.scheduling import services as scheduling
from apps.scheduling.models import Appointment
from apps.whatsapp import client

from . import replies
from .replies import ReplySet
from .text import contains_keyword, money, normalize

logger = logging.getLogger(__name__)

State = Conversation.State
LOCAL_TZ = scheduling.LOCAL_TZ

BOOKING_WORDS = ["agendar", "agendamento", "marcar", "reservar"]
CANCEL_WORDS = ["cancelar", "cancelamento", "remarcar"]
MENU_FAQ = {"2": replies.HOURS, "3": replies.PRICES, "4": replies.ADDRESS}
YES_WORDS = {"1", "sim", "s", "confirmar", "confirmo"}
NO_WORDS = {"2", "nao", "n", "outro"}
SKIP_WORDS = {"pular", "pula", "nao", "n"}

MAX_ACTIVE_APPOINTMENTS = 3
SEARCH_DAYS = 14   # até quantos dias à frente procuramos horários livres
DATES_OFFERED = 7  # quantos dias mostramos ao cliente
WEEKDAYS = ("Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom")

INVALID = "Opção inválida. Responda apenas com o número de uma das opções."
EMAIL_PROMPT = (
    "Quer receber a confirmação e o lembrete por e-mail? Informe seu e-mail abaixo. "
    "Ao informar, você concorda em usá-lo apenas para mensagens sobre seus agendamentos.\n\n"
    "Se preferir não informar, digite *pular*."
)


class StaleConversation(Exception):
    """O contexto guardado não faz mais sentido (serviço removido, dado ausente...)."""


# ---------------------------------------------------------------- entrada

def handle_message(message):
    """Processa uma mensagem recebida: atualiza o estado, grava e envia as respostas."""
    with transaction.atomic():
        conv = (
            Conversation.objects.select_related("customer__business")
            .select_for_update(of=("self",))  # uma mensagem por vez em cada conversa
            .get(pk=message.conversation_id)
        )
        texts = _process(conv, message.body)
        conv.save(update_fields=["state", "context", "updated_at"])
        Message.objects.bulk_create(
            [Message(conversation=conv, direction=Message.Direction.OUT, body=t) for t in texts]
        )

    # Rede só depois do commit: nenhuma trava de banco fica presa esperando a Meta.
    business = conv.customer.business
    for body in texts:
        try:
            client.send_text(
                phone_number_id=business.whatsapp_phone_number_id, to=conv.customer.phone, body=body
            )
        except client.WhatsAppSendError as exc:
            logger.error("bot: falha ao enviar resposta (%s)", exc)  # só código HTTP, sem dados pessoais
    logger.info("bot: estado=%s respostas=%d", conv.state, len(texts))


def _process(conv, raw):
    text = normalize(raw)
    leaving = text in {"0", "menu", "inicio"} or (conv.state != State.IDLE and text == "cancelar")
    if leaving:
        return _reset_to_menu(conv)
    try:
        return _HANDLERS[conv.state](conv, text, raw)
    except (StaleConversation, KeyError, ValueError, TypeError, IndexError) as exc:
        logger.warning("bot: contexto invalido, conversa reiniciada (%s)", type(exc).__name__)
        return _reset_to_menu(conv)


# ---------------------------------------------------------------- utilidades

def _set(conv, state, context=None):
    conv.state = state
    conv.context = context or {}


def _reset_to_menu(conv):
    _set(conv, State.IDLE)
    return [ReplySet(conv.customer.business).render(replies.GREETING)]


def _with_note(note, body):
    return f"{note}\n\n{body}" if note else body


def _fmt_day(day):
    return f"{WEEKDAYS[day.weekday()]} {day:%d/%m}"


def _choice(text, count):
    """'2' -> índice 1, se estiver entre 1 e count."""
    if re.fullmatch(r"[0-9]{1,2}", text):
        number = int(text)
        if 1 <= number <= count:
            return number - 1
    return None


def _parse_clock(text):
    """'14:30', '14h' ou '14h30' -> (14, 30)."""
    match = re.fullmatch(r"([0-9]{1,2})[:h]([0-9]{2})?", text)
    return (int(match[1]), int(match[2] or 0)) if match else None


def _context_service(conv):
    service = Service.objects.filter(
        pk=conv.context["service_id"], business=conv.customer.business, is_active=True
    ).first()
    if service is None:
        raise StaleConversation
    return service


# ---------------------------------------------------------------- estado: início

def _idle(conv, text, raw):
    business = conv.customer.business
    if contains_keyword(text, CANCEL_WORDS):
        phone = f" Telefone: {business.phone}" if business.phone else ""
        return [f"Para cancelar ou remarcar um agendamento, fale diretamente com o estabelecimento.{phone}"]
    if text == "1" or contains_keyword(text, BOOKING_WORDS):
        return _start_booking(conv)
    reply_set = ReplySet(business)
    intent = MENU_FAQ.get(text) or reply_set.detect(text) or replies.FALLBACK
    return [reply_set.render(intent)]


def _start_booking(conv):
    business = conv.customer.business
    active = Appointment.objects.filter(
        customer=conv.customer, status=Appointment.Status.CONFIRMED, start_at__gte=timezone.now()
    ).count()
    if active >= MAX_ACTIVE_APPOINTMENTS:
        _set(conv, State.IDLE)
        return [
            f"Você já tem {active} agendamentos ativos, que é o limite pelo WhatsApp. "
            "Para alterar ou cancelar, fale diretamente com o estabelecimento."
        ]
    ids = list(
        Service.objects.filter(business=business, is_active=True)
        .order_by("name")
        .values_list("pk", flat=True)
    )
    if not ids:
        _set(conv, State.IDLE)
        return ["No momento não há serviços disponíveis para agendamento. Fale diretamente com o estabelecimento."]
    _set(conv, State.CHOOSING_SERVICE, {"service_ids": ids})
    return [_service_prompt(conv)]


# ---------------------------------------------------------------- estado: serviço

def _service_prompt(conv, note=""):
    ids = conv.context["service_ids"]
    found = Service.objects.in_bulk(ids)
    lines = [
        f"*{i}* - {found[pk].name} ({found[pk].duration_minutes} min) - {money(found[pk].price)}"
        for i, pk in enumerate(ids, 1)
    ]
    body = "Qual serviço você deseja?\n" + "\n".join(lines)
    body += "\n\nDigite o número da opção. Para voltar ao menu, digite *0*."
    return _with_note(note, body)


def _choose_service(conv, text, raw):
    ids = conv.context["service_ids"]
    index = _choice(text, len(ids))
    if index is None:
        return [_service_prompt(conv, INVALID)]
    service = Service.objects.filter(
        pk=ids[index], business=conv.customer.business, is_active=True
    ).first()
    if service is None:
        return _start_booking(conv)
    return _show_dates(conv, service)


# ---------------------------------------------------------------- estado: dia

def _show_dates(conv, service, note=""):
    business = conv.customer.business
    now = timezone.now()
    today = now.astimezone(LOCAL_TZ).date()
    days = []
    for offset in range(SEARCH_DAYS + 1):
        day = today + dt.timedelta(days=offset)
        if scheduling.get_available_slots(business, service, day, now=now):
            days.append(day)
            if len(days) == DATES_OFFERED:
                break
    if not days:
        _set(conv, State.IDLE)
        return ["Não encontrei horários livres nos próximos dias. Fale diretamente com o estabelecimento. 🙏"]
    _set(conv, State.CHOOSING_DATE, {"service_id": service.pk, "dates": [d.isoformat() for d in days]})
    return [_date_prompt(conv, note)]


def _date_prompt(conv, note=""):
    days = [dt.date.fromisoformat(d) for d in conv.context["dates"]]
    lines = [f"*{i}* - {_fmt_day(day)}" for i, day in enumerate(days, 1)]
    body = "Para qual dia?\n" + "\n".join(lines)
    body += "\n\nDigite o número (ou a data, ex.: 10/11). Para voltar ao menu, digite *0*."
    return _with_note(note, body)


def _choose_date(conv, text, raw):
    days = [dt.date.fromisoformat(d) for d in conv.context["dates"]]
    day = None
    index = _choice(text, len(days))
    if index is not None:
        day = days[index]
    else:
        match = re.fullmatch(r"([0-9]{1,2})/([0-9]{1,2})", text)
        if match:
            wanted = (int(match[1]), int(match[2]))
            day = next((d for d in days if (d.day, d.month) == wanted), None)
    if day is None:
        return [_date_prompt(conv, INVALID)]
    return _show_times(conv, _context_service(conv), day)


# ---------------------------------------------------------------- estado: horário

def _show_times(conv, service, day, note=""):
    slots = scheduling.get_available_slots(conv.customer.business, service, day)
    if not slots:  # o dia lotou enquanto o cliente decidia
        return _show_dates(conv, service, note="Esse dia ficou sem horários livres.")
    _set(
        conv,
        State.CHOOSING_TIME,
        {"service_id": service.pk, "date": day.isoformat(), "slots": [s.isoformat() for s in slots]},
    )
    return [_time_prompt(conv, note)]


def _time_prompt(conv, note=""):
    day = dt.date.fromisoformat(conv.context["date"])
    slots = [dt.datetime.fromisoformat(s) for s in conv.context["slots"]]
    lines = [f"*{i}* - {slot.astimezone(LOCAL_TZ):%H:%M}" for i, slot in enumerate(slots, 1)]
    body = f"Horários livres em {_fmt_day(day)}:\n" + "\n".join(lines)
    body += "\n\nDigite o número (ou o horário, ex.: 14:30). Para voltar ao menu, digite *0*."
    return _with_note(note, body)


def _choose_time(conv, text, raw):
    slots = [dt.datetime.fromisoformat(s) for s in conv.context["slots"]]
    index = _choice(text, len(slots))
    if index is None:
        clock = _parse_clock(text)
        if clock:
            index = next(
                (
                    i
                    for i, slot in enumerate(slots)
                    if (slot.astimezone(LOCAL_TZ).hour, slot.astimezone(LOCAL_TZ).minute) == clock
                ),
                None,
            )
    if index is None:
        return [_time_prompt(conv, INVALID)]

    context = {"service_id": conv.context["service_id"], "start": slots[index].isoformat()}
    if conv.customer.email:  # já temos o e-mail: não perguntamos de novo
        _set(conv, State.CONFIRMING, context)
        return [_confirm_prompt(conv)]
    _set(conv, State.ASKING_EMAIL, context)
    return [EMAIL_PROMPT]


# ---------------------------------------------------------------- estado: e-mail

def _ask_email(conv, text, raw):
    if text not in SKIP_WORDS:
        email = raw.strip()
        try:
            if len(email) > 254:
                raise ValidationError("longo")
            validate_email(email)
        except ValidationError:
            return ["E-mail inválido. Digite um e-mail válido (ex.: nome@exemplo.com) ou *pular*."]
        customer = conv.customer
        customer.email = email
        customer.consent_at = timezone.now()  # LGPD: registra quando a pessoa informou
        customer.save(update_fields=["email", "consent_at"])
    _set(conv, State.CONFIRMING, conv.context)
    return [_confirm_prompt(conv)]


# ---------------------------------------------------------------- estado: confirmação

def _confirm_prompt(conv, note=""):
    service = _context_service(conv)
    start = dt.datetime.fromisoformat(conv.context["start"]).astimezone(LOCAL_TZ)
    body = (
        "Confirme seu agendamento:\n"
        f"*Serviço:* {service.name}\n"
        f"*Quando:* {_fmt_day(start.date())} às {start:%H:%M}\n"
        f"*Valor:* {money(service.price)}\n\n"
        "Responda *1* para confirmar ou *2* para escolher outro horário."
    )
    return _with_note(note, body)


def _confirm(conv, text, raw):
    if text in YES_WORDS:
        return _finalize(conv)
    if text in NO_WORDS:
        return _show_dates(conv, _context_service(conv))
    return [_confirm_prompt(conv, INVALID)]


def _finalize(conv):
    business = conv.customer.business
    service = _context_service(conv)
    start = dt.datetime.fromisoformat(conv.context["start"])
    try:
        appointment = scheduling.create_appointment(
            business=business, customer=conv.customer, service=service, start_at=start
        )
    except scheduling.SlotUnavailable:
        day = start.astimezone(LOCAL_TZ).date()
        return _show_times(conv, service, day, note="Que pena, esse horário ficou indisponível. Escolha outro:")
    except scheduling.InvalidRequest:
        raise StaleConversation from None

    _set(conv, State.IDLE)
    local = appointment.start_at.astimezone(LOCAL_TZ)
    lines = [
        "✅ *Agendamento confirmado!*",
        "",
        f"*Serviço:* {service.name}",
        f"*Quando:* {_fmt_day(local.date())} às {local:%H:%M}",
    ]
    if business.address:
        lines.append(f"*Local:* {business.address}")
    lines += ["", "Você receberá um lembrete antes do horário. Para voltar ao menu, digite *menu*."]
    return ["\n".join(lines)]


_HANDLERS = {
    State.IDLE.value: _idle,
    State.CHOOSING_SERVICE.value: _choose_service,
    State.CHOOSING_DATE.value: _choose_date,
    State.CHOOSING_TIME.value: _choose_time,
    State.ASKING_EMAIL.value: _ask_email,
    State.CONFIRMING.value: _confirm,
}