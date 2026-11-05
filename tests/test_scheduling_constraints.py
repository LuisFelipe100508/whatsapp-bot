import datetime as dt

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.businesses.models import Business, Service
from apps.customers.models import Customer
from apps.scheduling.models import Appointment

pytestmark = pytest.mark.django_db


@pytest.fixture
def ctx():
    owner = get_user_model().objects.create_user(username="dono")
    business = Business.objects.create(
        owner=owner, name="Barbearia Teste", whatsapp_phone_number_id="123456"
    )
    service = Service.objects.create(
        business=business, name="Corte", price="40.00", duration_minutes=30
    )
    customer = Customer.objects.create(business=business, phone="5535999999999")
    start = (timezone.now() + dt.timedelta(days=1)).replace(
        hour=13, minute=0, second=0, microsecond=0
    )
    return business, service, customer, start


def book(ctx, start, minutes=30, status=Appointment.Status.CONFIRMED):
    business, service, customer, _ = ctx
    return Appointment.objects.create(
        business=business,
        customer=customer,
        service=service,
        start_at=start,
        end_at=start + dt.timedelta(minutes=minutes),
        status=status,
    )


def test_overlapping_confirmed_appointment_is_rejected(ctx):
    start = ctx[3]
    book(ctx, start)
    with pytest.raises(IntegrityError), transaction.atomic():
        book(ctx, start + dt.timedelta(minutes=15))


def test_back_to_back_appointments_are_allowed(ctx):
    start = ctx[3]
    book(ctx, start)
    book(ctx, start + dt.timedelta(minutes=30))  # começa exatamente quando o outro termina


def test_cancelled_appointment_frees_the_slot(ctx):
    start = ctx[3]
    book(ctx, start, status=Appointment.Status.CANCELLED)
    book(ctx, start)  # mesmo horário, sem conflito


def test_end_must_be_after_start(ctx):
    start = ctx[3]
    with pytest.raises(IntegrityError), transaction.atomic():
        book(ctx, start, minutes=-10)