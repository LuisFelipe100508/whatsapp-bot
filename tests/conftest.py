import datetime as dt

import pytest
from django.contrib.auth import get_user_model

from apps.businesses.models import Business, BusinessHours, Service
from apps.customers.models import Customer


@pytest.fixture
def business(db):
    owner = get_user_model().objects.create_user(username="dono")
    biz = Business.objects.create(
        owner=owner, name="Barbearia Teste", whatsapp_phone_number_id="123456"
    )
    # Segunda-feira, 09:00 às 12:00
    BusinessHours.objects.create(
        business=biz, weekday=0, opens_at=dt.time(9, 0), closes_at=dt.time(12, 0)
    )
    return biz


@pytest.fixture
def service(business):
    return Service.objects.create(
        business=business, name="Corte", price="40.00", duration_minutes=30
    )


@pytest.fixture
def customer(business):
    return Customer.objects.create(
        business=business, phone="5535999999999", name="Cliente Teste"
    )