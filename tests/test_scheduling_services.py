import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from apps.businesses.models import Business, Service
from apps.scheduling import services
from apps.scheduling.models import Appointment

TZ = ZoneInfo("America/Sao_Paulo")
MONDAY = dt.date(2030, 1, 7)
NOW = dt.datetime(2030, 1, 6, 12, 0, tzinfo=TZ)  # domingo, véspera
assert MONDAY.weekday() == 0


def at(hour, minute=0):
    return dt.datetime.combine(MONDAY, dt.time(hour, minute), tzinfo=TZ)


def hm(slots):
    return [s.astimezone(TZ).strftime("%H:%M") for s in slots]


def book(business, customer, service, start, minutes=30):
    return Appointment.objects.create(
        business=business, customer=customer, service=service,
        start_at=start, end_at=start + dt.timedelta(minutes=minutes),
    )


def test_day_without_hours_has_no_slots(business, service):
    tuesday = MONDAY + dt.timedelta(days=1)
    assert services.get_available_slots(business, service, tuesday, now=NOW) == []


def test_slots_follow_grid_and_service_duration(business, service):
    slots = services.get_available_slots(business, service, MONDAY, now=NOW)
    assert hm(slots) == ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30"]

    long = Service.objects.create(
        business=business, name="Corte e barba", price="70.00", duration_minutes=60
    )
    assert hm(services.get_available_slots(business, long, MONDAY, now=NOW))[-1] == "11:00"


def test_booked_time_blocks_overlapping_slots(business, service, customer):
    book(business, customer, service, at(10), minutes=30)
    long = Service.objects.create(
        business=business, name="Corte e barba", price="70.00", duration_minutes=60
    )
    slots = services.get_available_slots(business, long, MONDAY, now=NOW)
    assert hm(slots) == ["09:00", "10:30", "11:00"]


def test_cancelled_appointment_does_not_block(business, service, customer):
    appt = book(business, customer, service, at(10))
    services.cancel_appointment(appt)
    assert "10:00" in hm(services.get_available_slots(business, service, MONDAY, now=NOW))


def test_minimum_notice_is_enforced(business, service):
    now = at(10, 20)  # antecedência mínima de 60 min -> a partir das 11:20
    assert hm(services.get_available_slots(business, service, MONDAY, now=now)) == ["11:30"]


def test_past_and_too_far_days_have_no_slots(business, service):
    next_day = dt.datetime(2030, 1, 8, 8, 0, tzinfo=TZ)
    assert services.get_available_slots(business, service, MONDAY, now=next_day) == []
    far = MONDAY + dt.timedelta(days=35)
    assert services.get_available_slots(business, service, far, now=NOW) == []


def test_create_appointment_success(business, service, customer):
    appt = services.create_appointment(
        business=business, customer=customer, service=service, start_at=at(10), now=NOW
    )
    assert appt.status == Appointment.Status.CONFIRMED
    assert appt.end_at == at(10, 30)


def test_create_rejects_off_grid_and_outside_hours(business, service, customer):
    for start in (at(9, 15), at(13, 0)):
        with pytest.raises(services.SlotUnavailable):
            services.create_appointment(
                business=business, customer=customer, service=service, start_at=start, now=NOW
            )


def test_create_rejects_naive_datetime(business, service, customer):
    naive = dt.datetime(2030, 1, 7, 10, 0)
    with pytest.raises(services.InvalidRequest):
        services.create_appointment(
            business=business, customer=customer, service=service, start_at=naive, now=NOW
        )


def test_create_rejects_service_from_another_business(business, customer):
    other = Business.objects.create(
        owner=business.owner, name="Outro", whatsapp_phone_number_id="999"
    )
    foreign_service = Service.objects.create(
        business=other, name="Corte", price="10.00", duration_minutes=30
    )
    with pytest.raises(services.InvalidRequest):
        services.create_appointment(
            business=business, customer=customer, service=foreign_service,
            start_at=at(10), now=NOW,
        )


def test_double_booking_is_rejected(business, service, customer):
    services.create_appointment(
        business=business, customer=customer, service=service, start_at=at(10), now=NOW
    )
    with pytest.raises(services.SlotUnavailable):
        services.create_appointment(
            business=business, customer=customer, service=service, start_at=at(10), now=NOW
        )


def test_database_constraint_is_the_safety_net(business, service, customer, monkeypatch):
    """Simula a corrida: a pré-checagem 'passa', mas o banco barra o conflito."""
    services.create_appointment(
        business=business, customer=customer, service=service, start_at=at(10), now=NOW
    )
    monkeypatch.setattr(services, "get_available_slots", lambda *a, **k: [at(10)])
    with pytest.raises(services.SlotUnavailable):
        services.create_appointment(
            business=business, customer=customer, service=service, start_at=at(10), now=NOW
        )
    assert Appointment.objects.count() == 1