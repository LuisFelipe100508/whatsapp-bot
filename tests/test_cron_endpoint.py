import pytest
from django.core.cache import cache
from rest_framework.throttling import ScopedRateThrottle

URL = "/cron/send-reminders/"
TOKEN = "t" * 48

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def cron_settings(settings):
    settings.REMINDER_CRON_TOKEN = TOKEN
    cache.clear()  # zera os contadores do rate limit


def call(client, token=TOKEN):
    extra = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token is not None else {}
    return client.post(URL, **extra)


def test_valid_token_runs_the_job(client):
    response = call(client)
    assert response.status_code == 200
    assert response.json() == {"sent": 0, "retry": 0, "failed": 0, "skipped": 0}


def test_wrong_token_is_rejected(client):
    assert call(client, "x" * 48).status_code == 403


def test_missing_header_is_rejected(client):
    assert call(client, None).status_code == 403


def test_fails_closed_when_token_not_configured(client, settings):
    settings.REMINDER_CRON_TOKEN = ""
    assert call(client, "").status_code == 403


def test_weak_token_is_refused_even_if_it_matches(client, settings):
    settings.REMINDER_CRON_TOKEN = "curto"
    assert call(client, "curto").status_code == 403


def test_get_is_not_allowed(client):
    assert client.get(URL, HTTP_AUTHORIZATION=f"Bearer {TOKEN}").status_code == 405


def test_rate_limit_returns_429(client, monkeypatch):
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "cron", "2/min")
    codes = [call(client).status_code for _ in range(3)]
    assert codes == [200, 200, 429]