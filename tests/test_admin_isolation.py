import datetime as dt
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.businesses.management.commands.create_owner_group import OWNER_GROUP
from apps.businesses.models import Business, Service
from apps.customers.models import Customer
from apps.scheduling.models import Appointment

pytestmark = pytest.mark.django_db


@pytest.fixture
def owners():
    call_command("create_owner_group")
    group = Group.objects.get(name=OWNER_GROUP)
    result = {}
    for key, label in (("a", "Alfa"), ("b", "Beta")):
        user = get_user_model().objects.create_user(username=f"dono_{key}", is_staff=True)
        user.groups.add(group)
        business = Business.objects.create(
            owner=user, name=f"Negocio {label}", whatsapp_phone_number_id=f"pn-{key}"
        )
        service = Service.objects.create(
            business=business, name="Corte", price="40.00", duration_minutes=30
        )
        customer = Customer.objects.create(
            business=business, phone=f"553599999000{1 if key == 'a' else 2}", name=f"Cliente {label}"
        )
        start = timezone.now() + dt.timedelta(days=2)
        appt = Appointment.objects.create(
            business=business, customer=customer, service=service,
            start_at=start, end_at=start + dt.timedelta(minutes=30),
        )
        result[key] = SimpleNamespace(user=user, business=business, appt=appt)
    return SimpleNamespace(**result)


def test_owner_sees_only_own_appointments(client, owners):
    client.force_login(owners.a.user)
    response = client.get(reverse("admin:scheduling_appointment_changelist"))
    body = response.content.decode()
    assert response.status_code == 200
    assert "Cliente Alfa" in body
    assert "Cliente Beta" not in body


def test_owner_cannot_open_another_owners_appointment(client, owners):
    client.force_login(owners.a.user)
    url = reverse("admin:scheduling_appointment_change", args=[owners.b.appt.pk])
    assert client.get(url).status_code != 200


def test_owner_sees_only_own_business(client, owners):
    client.force_login(owners.a.user)
    body = client.get(reverse("admin:businesses_business_changelist")).content.decode()
    assert "Negocio Alfa" in body
    assert "Negocio Beta" not in body

    url = reverse("admin:businesses_business_change", args=[owners.b.business.pk])
    assert client.get(url).status_code != 200


def test_owner_cannot_create_business_or_appointment(client, owners):
    client.force_login(owners.a.user)
    assert client.get(reverse("admin:businesses_business_add")).status_code == 403
    assert client.get(reverse("admin:scheduling_appointment_add")).status_code == 403