from apps.bot.text import money
from apps.scheduling.services import LOCAL_TZ

WEEKDAYS = (
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
)


def one_line(text) -> str:
    """Uma linha só: sem quebras nem espaços repetidos (e-mail e parâmetros de template)."""
    return " ".join(str(text).split())


def local_start(appointment):
    return appointment.start_at.astimezone(LOCAL_TZ)


def when(appointment) -> str:
    local = local_start(appointment)
    return f"{WEEKDAYS[local.weekday()]}, {local:%d/%m/%Y} às {local:%H:%M}"


def _place_lines(business):
    lines = []
    if business.address:
        lines.append(f"Local: {business.address}")
    if business.phone:
        lines.append(f"Contato: {business.phone}")
    return lines


def confirmation_email(appointment):
    business = appointment.business
    subject = one_line(f"Agendamento confirmado - {business.name}")
    lines = [
        "Olá! Seu agendamento está confirmado.",
        "",
        f"Estabelecimento: {business.name}",
        f"Serviço: {appointment.service.name}",
        f"Quando: {when(appointment)}",
        f"Valor: {money(appointment.service.price)}",
        *_place_lines(business),
        "",
        "Você receberá um lembrete antes do horário.",
        "Para remarcar ou cancelar, fale diretamente com o estabelecimento.",
        "",
        "Este e-mail foi enviado porque você o informou ao agendar pelo WhatsApp.",
    ]
    return subject, "\n".join(lines)


def reminder_email(appointment):
    business = appointment.business
    subject = one_line(f"Lembrete do seu horário - {business.name}")
    lines = [
        "Olá! Este é um lembrete do seu horário.",
        "",
        f"Estabelecimento: {business.name}",
        f"Serviço: {appointment.service.name}",
        f"Quando: {when(appointment)}",
        *_place_lines(business),
        "",
        "Para remarcar ou cancelar, fale diretamente com o estabelecimento.",
    ]
    return subject, "\n".join(lines)


def reminder_whatsapp_text(appointment) -> str:
    business = appointment.business
    lines = [
        f"⏰ *Lembrete:* você tem *{appointment.service.name}* agendado em {when(appointment)} "
        f"em *{business.name}*.",
    ]
    if business.address:
        lines.append(f"📍 {business.address}")
    lines += ["", "Para remarcar ou cancelar, fale diretamente com o estabelecimento."]
    return "\n".join(lines)


def template_params(appointment) -> list:
    """Variáveis do template: {{1}} serviço, {{2}} dia (dd/mm), {{3}} hora, {{4}} estabelecimento."""
    local = local_start(appointment)
    return [
        one_line(appointment.service.name)[:100],
        f"{local:%d/%m}",
        f"{local:%H:%M}",
        one_line(appointment.business.name)[:100],
    ]