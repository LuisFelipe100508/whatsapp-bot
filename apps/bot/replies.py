import re

from .models import BotReply
from .text import contains_keyword, money, split_keywords

Intent = BotReply.Intent
GREETING = Intent.GREETING.value
HOURS = Intent.HOURS.value
PRICES = Intent.PRICES.value
ADDRESS = Intent.ADDRESS.value
FALLBACK = Intent.FALLBACK.value

MENU = (
    "Digite o número da opção:\n"
    "*1* - Agendar horário\n"
    "*2* - Horário de funcionamento\n"
    "*3* - Serviços e preços\n"
    "*4* - Endereço"
)

DEFAULTS = {
    GREETING: {
        "keywords": "oi, ola, bom dia, boa tarde, boa noite, menu, inicio, ajuda",
        "text": "Olá! 👋 Aqui é o atendimento virtual de *{nome}*.\n\n{menu}",
    },
    HOURS: {
        "keywords": "horario, horarios, funcionamento, abre, fecha, aberto, funciona",
        "text": "🕘 *Horário de funcionamento*\n{horarios}\n\nPara agendar, digite *1*.",
    },
    PRICES: {
        "keywords": "preco, precos, valor, valores, quanto, custa, servicos, tabela",
        "text": "💈 *Serviços e preços*\n{precos}\n\nPara agendar, digite *1*.",
    },
    ADDRESS: {
        "keywords": "endereco, local, onde, localizacao, como chegar",
        "text": "📍 *Endereço*\n{endereco}",
    },
    FALLBACK: {
        "keywords": "",
        "text": "Desculpe, não entendi. 😕\n\n{menu}",
    },
}

FAQ_ORDER = (ADDRESS, PRICES, HOURS, GREETING)  # a pergunta específica vence a saudação
ALWAYS_ON = {GREETING, FALLBACK}  # o bot sempre precisa saber cumprimentar e pedir desculpa
PLACEHOLDER = re.compile(r"\{(nome|horarios|precos|endereco|menu)\}")


class ReplySet:
    """Respostas de um negócio: o que o dono editou, com os padrões como reserva."""

    def __init__(self, business):
        self.business = business
        rows = {row.intent: row for row in BotReply.objects.filter(business=business)}
        self._entries = {}
        for intent, default in DEFAULTS.items():
            row = rows.get(intent)
            if row is None or (not row.is_active and intent in ALWAYS_ON):
                self._entries[intent] = (default["keywords"], default["text"], True)
            else:
                self._entries[intent] = (row.keywords, row.text, row.is_active)

    def detect(self, normalized_text: str):
        for intent in FAQ_ORDER:
            keywords, _, enabled = self._entries[intent]
            if enabled and contains_keyword(normalized_text, split_keywords(keywords)):
                return intent
        return None

    def render(self, intent: str) -> str:
        _, text, enabled = self._entries[intent]
        if not enabled:  # assunto desligado pelo dono
            text = self._entries[FALLBACK][1]
        return self._fill(text)

    def _fill(self, template: str) -> str:
        values = {
            "nome": lambda: self.business.name,
            "menu": lambda: MENU,
            "horarios": self._hours_text,
            "precos": self._prices_text,
            "endereco": lambda: self.business.address or "Endereço não informado.",
        }
        # Uma única passada: o que entra no lugar de um placeholder nunca é re-interpretado.
        return PLACEHOLDER.sub(lambda match: values[match.group(1)](), template)

    def _hours_text(self) -> str:
        lines = [
            f"{h.get_weekday_display()}: {h.opens_at:%H:%M} às {h.closes_at:%H:%M}"
            for h in self.business.hours.all()
        ]
        return "\n".join(lines) or "Consulte-nos para saber os horários."

    def _prices_text(self) -> str:
        services = self.business.services.filter(is_active=True).order_by("name")
        lines = [f"• {s.name} ({s.duration_minutes} min): {money(s.price)}" for s in services]
        return "\n".join(lines) or "Consulte-nos para saber os valores."