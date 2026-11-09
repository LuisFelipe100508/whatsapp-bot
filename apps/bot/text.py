import re
import unicodedata


def normalize(text: str) -> str:
    """Minúsculas, sem acentos, espaços simplificados: 'Horário?' -> 'horario?'."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", without_accents).strip()


def split_keywords(raw: str) -> list[str]:
    parts = raw.replace("\n", ",").split(",")
    return [k for k in (normalize(p) for p in parts) if k]


def contains_keyword(normalized_text: str, keywords) -> bool:
    """Palavra ou frase inteira: 'marcar' não casa com 'remarcar'."""
    return any(
        re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", normalized_text) for keyword in keywords
    )


def money(value) -> str:
    return f"R$ {value:.2f}".replace(".", ",")