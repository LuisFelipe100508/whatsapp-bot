from io import StringIO

import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db


def test_command_reports_counts():
    out = StringIO()
    call_command("send_reminders", stdout=out)
    assert "enviados=0" in out.getvalue()