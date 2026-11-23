from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import uuid

import pytest

import app as application

original_send_booking_confirmation = application.send_booking_confirmation


def test_customer_registration_opens_the_new_account():
    email = f'new-customer-{uuid.uuid4().hex}@example.test'
    client = application.app.test_client()

    try:
        response = client.post('/register', data={
            'name': 'New Customer',
            'email': email,
            'password': 'customer-test-password',
            'confirm_password': 'customer-test-password',
        })

        assert response.status_code == 302
        assert response.headers['Location'].endswith('/my-bookings')
        profile_response = client.get('/api/customer/profile')
        assert profile_response.status_code == 200
        assert profile_response.get_json()['customer']['name'] == 'New Customer'
        assert profile_response.get_json()['customer']['email'] == email
    finally:
        with application.app.app_context():
            user = application.User.query.filter_by(email=email).first()
            if user:
                application.db.session.delete(user)
                application.db.session.commit()


@pytest.fixture
def customer_trip(monkeypatch):
    monkeypatch.setattr(application, 'is_paystack_configured', lambda: True)
    email = f'customer-{uuid.uuid4().hex}@example.test'
    slug = f'customer-trip-{uuid.uuid4().hex}'
    with application.app.app_context():
        user = application.User(
            name='Booking Customer',
            email=email,
            password_hash=application.generate_password_hash('customer-test-password'),
        )
        tour = application.Tour(
            slug=slug,
            name='Customer Test Island Tour',
            description='A tour used to test the customer booking flow.',
            duration='Two hours',
            price=1500,
            category='Dhow & Island Hopping',
            itinerary='Meet your guide\nSail along the coast',
            inclusions='Local guide',
            exclusions='Meals',
            pickup_point='kenyaBook meeting point',
            min_group_size=1,
            max_group_size=6,
        )
        application.db.session.add_all([user, tour])
        application.db.session.commit()
        user_id = user.id

        start = (datetime.now(ZoneInfo('Africa/Nairobi')).replace(tzinfo=None) + timedelta(days=6)).replace(second=0, microsecond=0)
        near_start = (datetime.now(ZoneInfo('Africa/Nairobi')).replace(tzinfo=None) + timedelta(hours=24)).replace(second=0, microsecond=0)
        slots = [
            application.TourSchedule(tour_slug=slug, starts_at=start, capacity=4),
            application.TourSchedule(tour_slug=slug, starts_at=start + timedelta(days=1), capacity=4),
            application.TourSchedule(tour_slug=slug, starts_at=near_start, capacity=2),
        ]
        application.db.session.add_all(slots)
        application.db.session.commit()
        schedule_ids = [slot.id for slot in slots]

    monkeypatch.setattr(application, 'send_booking_confirmation', lambda booking, **kwargs: True)

    def initialize_paystack(**kwargs):
        return {
            'reference': kwargs['reference'],
            'authorization_url': 'https://checkout.paystack.com/customer-test',
            'access_code': 'access_test',
            'customer_message': 'Continue to Paystack.',
        }

    monkeypatch.setattr(application, 'initialize_paystack_transaction', initialize_paystack)
    client = application.app.test_client()
    response = client.post('/login', data={'email': email, 'password': 'customer-test-password'})
    assert response.status_code == 302
    with client.session_transaction() as session:
        csrf_token = session['customer_csrf']

    yield {
        'client': client,
        'csrf': csrf_token,
        'email': email,
        'slug': slug,
        'user_id': user_id,
        'schedule_ids': schedule_ids,
        'starts_at': start,
    }

    with application.app.app_context():
        application.Booking.query.filter_by(user_id=user_id).delete()
        application.TourSchedule.query.filter_by(tour_slug=slug).delete()
        application.db.session.delete(application.db.session.get(application.Tour, slug))
        application.db.session.delete(application.db.session.get(application.User, user_id))
        application.db.session.commit()


def booking_payload(trip, schedule_id, guests=1, **overrides):
    payload = {
        'name': 'Booking Customer',
        'email': trip['email'],
        'contact_phone': '+254 712 345 678',
        'tour': trip['slug'],
        'schedule_id': schedule_id,
        'guests': guests,
        'date': 'ignored-for-scheduled-tour',
        'time': 'ignored-for-scheduled-tour',
        'message': '',
    }
    payload.update(overrides)
    return payload


def test_customer_can_book_view_reschedule_and_cancel_while_capacity_is_reserved(customer_trip):
    trip = customer_trip
    client = trip['client']
    first_slot, second_slot, _ = trip['schedule_ids']
    response = client.post('/booking-confirmation', json=booking_payload(trip, first_slot, guests=2))

    assert response.status_code == 201
    result = response.get_json()
    booking_id = result['booking']['id']
    assert result['email_sent'] is True
    assert result['managed'] is True
    assert result['booking']['status'] == 'requested'
    assert result['booking']['payment_status'] == 'pending'
    assert result['payment_reference']
    assert result['payment_method'] == 'paystack'
    assert result['authorization_url'] == 'https://checkout.paystack.com/customer-test'
    assert result['booking']['date'] == trip['starts_at'].date().isoformat()

    with application.app.app_context():
        assert application.db.session.get(application.TourSchedule, first_slot).booked_count == 2
        saved_booking = application.db.session.get(application.Booking, booking_id)
        assert saved_booking.commission_rate == float(application.get_admin_setting('host_commission_rate', 4))
        # The guest pays the published subtotal plus the 9% service fee and the
        # flat booking fee.
        assert saved_booking.subtotal_amount == 3000
        assert saved_booking.service_fee_amount == 270
        assert saved_booking.booking_fee_amount == 100
        assert saved_booking.amount == 3370
        assert saved_booking.host_payout_amount == 2880

    response = client.get('/api/customer/bookings')
    assert response.status_code == 200
    assert [booking['id'] for booking in response.get_json()['bookings']] == [booking_id]

    other_client = application.app.test_client()
    assert other_client.get('/api/customer/bookings').status_code == 401

    response = client.post(
        f'/api/customer/bookings/{booking_id}/reschedule',
        json={'schedule_id': second_slot},
        headers={'X-CSRF-Token': trip['csrf']},
    )
    assert response.status_code == 200
    assert response.get_json()['booking']['schedule_id'] == second_slot
    with application.app.app_context():
        assert application.db.session.get(application.TourSchedule, first_slot).booked_count == 0
        assert application.db.session.get(application.TourSchedule, second_slot).booked_count == 2

    response = client.post(
        f'/api/customer/bookings/{booking_id}/cancel',
        headers={'X-CSRF-Token': trip['csrf']},
    )
    assert response.status_code == 409
    assert 'payment request is still pending' in response.get_json()['error']
    with application.app.app_context():
        assert application.db.session.get(application.TourSchedule, second_slot).booked_count == 2


def test_capacity_is_enforced_and_customer_changes_are_blocked_inside_48_hours(customer_trip):
    trip = customer_trip
    client = trip['client']
    _, _, limited_slot = trip['schedule_ids']
    payload = booking_payload(trip, limited_slot, guests=2)

    response = client.post('/booking-confirmation', json=payload)
    assert response.status_code == 201
    available = client.get(f"/api/tours/{trip['slug']}/availability").get_json()['schedules']
    assert limited_slot not in {item['id'] for item in available}
    assert client.post('/booking-confirmation', json=payload).status_code == 409

    booking_id = response.get_json()['booking']['id']
    blocked = client.post(
        f'/api/customer/bookings/{booking_id}/cancel',
        headers={'X-CSRF-Token': trip['csrf']},
    )
    assert blocked.status_code == 409
    assert 'payment request is still pending' in blocked.get_json()['error']


def test_booking_requires_a_valid_departure_and_customer_csrf(customer_trip):
    trip = customer_trip
    client = trip['client']
    payload = booking_payload(trip, 999999)

    response = client.post('/booking-confirmation', json=payload)
    assert response.status_code == 400

    booked = client.post('/booking-confirmation', json=booking_payload(trip, trip['schedule_ids'][0]))
    assert booked.status_code == 201
    booking_id = booked.get_json()['booking']['id']
    assert client.post(f'/api/customer/bookings/{booking_id}/cancel').status_code == 403


def test_booking_is_blocked_when_paystack_is_not_configured(customer_trip, monkeypatch):
    trip = customer_trip
    monkeypatch.setattr(application, 'is_paystack_configured', lambda: False)

    response = trip['client'].post(
        '/booking-confirmation',
        json=booking_payload(trip, trip['schedule_ids'][0]),
    )

    assert response.status_code == 503
    with application.app.app_context():
        assert application.Booking.query.filter_by(user_id=trip['user_id']).count() == 0
        assert application.db.session.get(application.TourSchedule, trip['schedule_ids'][0]).booked_count == 0


def test_paystack_callback_marks_paid_and_emails_the_receipt(customer_trip, monkeypatch):
    trip = customer_trip
    response = trip['client'].post(
        '/booking-confirmation',
        json=booking_payload(trip, trip['schedule_ids'][0]),
    )
    booking_data = response.get_json()['booking']
    with application.app.app_context():
        booking = application.db.session.get(application.Booking, booking_data['id'])
        transaction = {
            'reference': booking.paystack_reference,
            'status': 'success',
            'currency': 'KES',
            'amount': int(round(booking.amount)) * 100,
            'channel': 'card',
        }
        paystack_reference = booking.paystack_reference
    monkeypatch.setattr(application, 'verify_paystack_transaction', lambda reference: transaction)
    sent_messages = []

    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def ehlo(self):
            pass

        def login(self, *args):
            pass

        def send_message(self, message):
            sent_messages.append(message)

    monkeypatch.setattr(application, 'EMAIL_HOST', 'smtp.example.test')
    monkeypatch.setattr(application, 'EMAIL_USERNAME', 'mailer@example.test')
    monkeypatch.setattr(application, 'EMAIL_PASSWORD', 'test-password')
    monkeypatch.setattr(application, 'EMAIL_FROM', 'mailer@example.test')
    monkeypatch.setattr(application, 'EMAIL_USE_SSL', False)
    monkeypatch.setattr(application, 'EMAIL_USE_TLS', False)
    monkeypatch.setattr(application.smtplib, 'SMTP', FakeSMTP)
    monkeypatch.setattr(application, 'send_booking_confirmation', original_send_booking_confirmation)

    result = trip['client'].get(
        '/paystack/callback', query_string={'reference': paystack_reference}
    )

    assert result.status_code == 302
    with application.app.app_context():
        booking = application.db.session.get(application.Booking, booking_data['id'])
        assert booking.payment_status == 'paid'
        assert booking.status == 'confirmed'
        assert booking.payment_method == 'paystack'
        assert application.booking_payment_receipt(booking) == paystack_reference
        assert booking.payment_confirmed_at is not None
    payment_reference = response.get_json()['payment_reference']
    documents = trip['client'].get(f'/api/payment-status/{payment_reference}').get_json()['document_urls']
    assert documents['receipt']
    for document_type in ('invoice', 'receipt'):
        document = trip['client'].get(documents[document_type])
        assert document.status_code == 200
        assert document.mimetype == 'application/pdf'
        assert document.data.startswith(b'%PDF-')
    attachments = list(sent_messages[0].iter_attachments())
    assert {attachment.get_filename() for attachment in attachments} == {
        f"kenyaBook-Invoice-{booking_data['id']}.pdf",
        f"kenyaBook-Receipt-{booking_data['id']}.pdf",
    }


def test_payment_status_requires_opaque_booking_reference(customer_trip):
    trip = customer_trip
    response = trip['client'].post(
        '/booking-confirmation',
        json=booking_payload(trip, trip['schedule_ids'][0]),
    )
    payment_reference = response.get_json()['payment_reference']

    result = trip['client'].get(f'/api/payment-status/{payment_reference}')
    assert result.status_code == 200
    assert result.get_json()['payment_status'] == 'pending'
    documents = result.get_json()['document_urls']
    assert documents['invoice']
    assert documents['receipt'] is None
    assert trip['client'].get(documents['invoice']).status_code == 200
    assert trip['client'].get(f'/api/payment-documents/{payment_reference}/receipt').status_code == 404
    assert trip['client'].get('/api/payment-status/not-a-reference').status_code == 404


def test_international_phone_numbers_are_accepted_for_paystack_bookings(customer_trip):
    trip = customer_trip
    payload = booking_payload(
        trip,
        trip['schedule_ids'][0],
        contact_phone='+44 7700 900123',
        country_of_residence='United Kingdom',
    )

    response = trip['client'].post('/booking-confirmation', json=payload)

    assert response.status_code == 201, response.get_json()
    assert response.get_json()['booking']['phone'] == '+44 7700 900123'
    assert response.get_json()['payment_method'] == 'paystack'
