import pytest
from django.core.management import call_command

from apps.bot.models import BotReply
from apps.businesses.models import Service

pytestmark = pytest.mark.django_db


def test_greeting_shows_menu(say):
    reply = say("Oi")
    assert "Barbearia Teste" in reply
    assert "*1* - Agendar horário" in reply


def test_menu_option_2_shows_business_hours(say):
    assert "Segunda-feira: 09:00 às 12:00" in say("2")


def test_menu_option_3_shows_services_and_prices(say, service):
    reply = say("3")
    assert "Corte" in reply
    assert "R$ 40,00" in reply


def test_address_by_keyword(say, business):
    business.address = "Rua das Flores, 10"
    business.save()
    assert "Rua das Flores, 10" in say("Onde vocês ficam?")


def test_keywords_ignore_accents_and_case(say):
    assert "Segunda-feira: 09:00 às 12:00" in say("QUAL O HORÁRIO DE FUNCIONAMENTO?")


def test_specific_question_wins_over_greeting(say, service):
    assert "R$ 40,00" in say("Bom dia, quanto custa?")


def test_unknown_text_gets_fallback(say):
    reply = say("asdfgh")
    assert "não entendi" in reply
    assert "*1* - Agendar horário" in reply


def test_owner_can_edit_reply_and_keywords(say, business):
    BotReply.objects.create(
        business=business,
        intent=BotReply.Intent.HOURS,
        keywords="expediente",
        text="Abrimos assim:\n{horarios}",
    )
    reply = say("Qual o expediente de vocês?")
    assert reply.startswith("Abrimos assim:")
    assert "Segunda-feira: 09:00 às 12:00" in reply


def test_disabled_reply_is_not_used(say, business):
    BotReply.objects.create(
        business=business, intent=BotReply.Intent.HOURS, keywords="horario", text="x", is_active=False
    )
    assert "não entendi" in say("horario")


def test_placeholders_are_filled_in_a_single_pass(say, business):
    business.address = "Rua Secreta, 1"
    business.save()
    Service.objects.create(business=business, name="{endereco}", price="10.00", duration_minutes=30)
    reply = say("3")
    assert "{endereco}" in reply  # o nome do serviço aparece literal
    assert "Rua Secreta" not in reply  # e não é re-interpretado como placeholder


def test_cancel_request_points_to_the_business(say, business):
    business.phone = "(35) 99999-0000"
    business.save()
    assert "(35) 99999-0000" in say("quero cancelar meu horário")


def test_seed_is_idempotent_and_keeps_owner_edits(business):
    call_command("seed_bot_replies")
    assert BotReply.objects.filter(business=business).count() == 5
    BotReply.objects.filter(business=business, intent="hours").update(text="Texto do dono")
    call_command("seed_bot_replies")
    assert BotReply.objects.filter(business=business).count() == 5
    assert BotReply.objects.get(business=business, intent="hours").text == "Texto do dono"