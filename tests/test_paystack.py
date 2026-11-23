import hashlib
import hmac
import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text

import app as application
from saas.modules.bookings import paystack


@pytest.fixture
def paystack_environment(monkeypatch):
    values = {
        'PAYSTACK_SECRET_KEY': 'sk_test_paystack_secret',
        'PAYSTACK_CALLBACK_URL': 'https://example.com/paystack/callback',
        'PAYSTACK_WEBHOOK_SECRET': 'whsec_test_webhook_secret',
        'SITE_URL': 'https://example.com',
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return values


def test_paystack_initialization_sends_minor_units_and_server_metadata(paystack_environment, monkeypatch):
    calls = []

    def request_json(config, path, **kwargs):
        calls.append((config, path, kwargs))
        return {
            'reference': kwargs['payload']['reference'],
            'access_code': 'access_test',
            'authorization_url': 'https://checkout.paystack.com/test-checkout',
        }

    monkeypatch.setattr(paystack, '_request_json', request_json)

    result = paystack.initialize_transaction(
        email='guest@example.test',
        amount=1735,
        reference='KB-B1-test',
        metadata={'booking_id': 1, 'kind': 'booking'},
    )

    config, path, request = calls[0]
    assert config['secret_key'] == 'sk_test_paystack_secret'
    assert path == '/transaction/initialize'
    assert request['method'] == 'POST'
    assert request['payload'] == {
        'email': 'guest@example.test',
        'amount': 173500,
        'currency': 'KES',
        'reference': 'KB-B1-test',
        'callback_url': 'https://example.com/paystack/callback',
        'metadata': {'booking_id': 1, 'kind': 'booking'},
    }
    assert result['authorization_url'] == 'https://checkout.paystack.com/test-checkout'


def test_paystack_initialization_rejects_an_untrusted_checkout(paystack_environment, monkeypatch):
    monkeypatch.setattr(paystack, '_request_json', lambda *args, **kwargs: {
        'reference': kwargs['payload']['reference'],
        'access_code': 'access_test',
        'authorization_url': 'https://attacker.example/checkout',
    })

    with pytest.raises(paystack.PaystackError) as error:
        paystack.initialize_transaction(
            email='guest@example.test',
            amount=1000,
            reference='KB-B1-test',
            metadata={},
        )

    assert error.value.outcome_unknown is True


def test_paystack_verification_escapes_the_reference(paystack_environment, monkeypatch):
    calls = []

    def request_json(config, path, **kwargs):
        calls.append(path)
        return {'reference': 'KB/B1-test', 'status': 'success', 'currency': 'KES', 'amount': 100000}

    monkeypatch.setattr(paystack, '_request_json', request_json)

    result = paystack.verify_transaction('KB/B1-test')

    assert calls == ['/transaction/verify/KB%2FB1-test']
    assert result['status'] == 'success'


def test_paystack_configuration_requires_a_public_https_callback(paystack_environment, monkeypatch):
    monkeypatch.setenv('PAYSTACK_CALLBACK_URL', 'http://localhost/paystack/callback')

    assert paystack.is_configured() is False
    with pytest.raises(paystack.PaystackError, match='publicly reachable HTTPS'):
        paystack.initialize_transaction(
            email='guest@example.test', amount=1000, reference='KB-B1-test', metadata={}
        )


def test_paystack_callback_defaults_to_the_site_url(paystack_environment, monkeypatch):
    monkeypatch.delenv('PAYSTACK_CALLBACK_URL')

    assert paystack.is_configured() is True
    assert paystack._configuration()['callback_url'] == 'https://example.com/paystack/callback'


def test_paystack_legacy_webhook_signature(paystack_environment):
    raw_body = b'{"event":"charge.success"}'
    signature = hmac.new(
        paystack_environment['PAYSTACK_SECRET_KEY'].encode(), raw_body, hashlib.sha512
    ).hexdigest()

    assert paystack.verify_webhook_signature(raw_body, legacy_header=signature) is True
    assert paystack.verify_webhook_signature(raw_body, legacy_header='0' * 128) is False


def test_paystack_current_webhook_signature_and_replay_window(paystack_environment):
    timestamp = 1_800_000_000
    raw_body = b'{"event":"charge.success"}'
    signature = hmac.new(
        paystack_environment['PAYSTACK_WEBHOOK_SECRET'].encode(),
        f'{timestamp}.'.encode() + raw_body,
        hashlib.sha512,
    ).hexdigest()
    header = f't={timestamp},v1=whk_test:{signature}'

    assert paystack.verify_webhook_signature(
        raw_body, current_header=header, now=timestamp
    ) is True
    assert paystack.verify_webhook_signature(
        raw_body, current_header=header, now=timestamp + 301
    ) is False


def test_paystack_request_rejects_non_transaction_paths(paystack_environment):
    with pytest.raises(paystack.PaystackError, match='URL is not allowed'):
        paystack._request_json(paystack._configuration(), '/customer/create')


@pytest.fixture
def paystack_tour(monkeypatch, paystack_environment):
    monkeypatch.setattr(application, 'is_paystack_configured', lambda: True)
    monkeypatch.setattr(application, 'send_booking_confirmation', lambda booking, **kwargs: True)
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        return {
            'reference': kwargs['reference'],
            'authorization_url': 'https://checkout.paystack.com/test-checkout',
            'access_code': 'access_test',
            'customer_message': 'Continue to Paystack.',
        }

    monkeypatch.setattr(application, 'initialize_paystack_transaction', initialize)
    slug = f'paystack-tour-{uuid.uuid4().hex}'
    email = f'paystack-{uuid.uuid4().hex}@example.test'
    with application.app.app_context():
        tour = application.Tour(
            slug=slug,
            name='Paystack Test Tour',
            description='A tour used to test Paystack booking payments.',
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
        application.db.session.add(tour)
        application.db.session.commit()
        starts_at = (
            datetime.now(ZoneInfo('Africa/Nairobi')).replace(tzinfo=None) + timedelta(days=7)
        ).replace(second=0, microsecond=0)
        schedule = application.TourSchedule(tour_slug=slug, starts_at=starts_at, capacity=4)
        application.db.session.add(schedule)
        application.db.session.commit()
        schedule_id = schedule.id

    yield {
        'client': application.app.test_client(),
        'slug': slug,
        'email': email,
        'schedule_id': schedule_id,
        'captured': captured,
    }

    with application.app.app_context():
        application.Booking.query.filter_by(tour=slug).delete()
        application.TourSchedule.query.filter_by(tour_slug=slug).delete()
        application.db.session.delete(application.db.session.get(application.Tour, slug))
        application.db.session.commit()


def _booking_payload(tour, **overrides):
    payload = {
        'name': 'Paystack Guest',
        'email': tour['email'],
        'contact_phone': '+254 712 345 678',
        'payment_method': 'paystack',
        'tour': tour['slug'],
        'schedule_id': tour['schedule_id'],
        'guests': 1,
        'date': 'ignored-for-scheduled-tour',
        'time': 'ignored-for-scheduled-tour',
        'message': '',
    }
    payload.update(overrides)
    return payload


def _start_booking(tour):
    response = tour['client'].post('/booking-confirmation', json=_booking_payload(tour))
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def _transaction(booking, **overrides):
    transaction = {
        'reference': booking.paystack_reference,
        'status': 'success',
        'currency': 'KES',
        'amount': int(round(booking.amount)) * 100,
        'channel': 'card',
        'gateway_response': 'Successful payment',
    }
    transaction.update(overrides)
    return transaction


def _legacy_webhook(client, payload, secret='sk_test_paystack_secret', signature=None):
    raw_body = json.dumps(payload, separators=(',', ':')).encode()
    if signature is None:
        signature = hmac.new(secret.encode(), raw_body, hashlib.sha512).hexdigest()
    return client.post(
        '/paystack/webhook',
        data=raw_body,
        content_type='application/json',
        headers={'x-paystack-signature': signature},
    )


def test_paystack_booking_initializes_with_a_saved_reference(paystack_tour):
    result = _start_booking(paystack_tour)
    captured = paystack_tour['captured']

    assert result['payment_method'] == 'paystack'
    assert result['authorization_url'] == 'https://checkout.paystack.com/test-checkout'
    assert result['booking']['phone'] == '+254 712 345 678'
    assert result['booking']['paystack_reference'] == captured['reference']
    assert captured['email'] == paystack_tour['email']
    assert captured['amount'] == result['booking']['amount']
    assert captured['metadata']['kind'] == 'booking'
    with application.app.app_context():
        booking = application.Booking.query.filter_by(id=result['booking']['id']).one()
        assert booking.paystack_reference == captured['reference']
        assert booking.payment_status == 'pending'
        assert application.db.session.get(
            application.TourSchedule, paystack_tour['schedule_id']
        ).booked_count == 1


def test_paystack_booking_defaults_to_paystack_when_method_is_omitted(paystack_tour):
    payload = _booking_payload(paystack_tour)
    payload.pop('payment_method')

    response = paystack_tour['client'].post('/booking-confirmation', json=payload)

    assert response.status_code == 201, response.get_json()
    assert response.get_json()['payment_method'] == 'paystack'
    assert response.get_json()['booking']['payment_method'] == 'paystack'


def test_international_traveler_books_directly_through_paystack(paystack_tour):
    response = paystack_tour['client'].post('/booking-confirmation', json=_booking_payload(
        paystack_tour,
        contact_phone='+44 7700 900123',
        country_of_residence='United Kingdom',
    ))

    assert response.status_code == 201, response.get_json()
    result = response.get_json()
    assert result['authorization_url'] == 'https://checkout.paystack.com/test-checkout'
    assert result['booking']['phone'] == '+44 7700 900123'
    assert paystack_tour['captured']['email'] == paystack_tour['email']


def test_paystack_booking_rejects_invalid_method_and_missing_configuration(paystack_tour, monkeypatch):
    for method in ('card', 'mpesa'):
        invalid = paystack_tour['client'].post(
            '/booking-confirmation', json=_booking_payload(paystack_tour, payment_method=method)
        )
        assert invalid.status_code == 400
        assert invalid.get_json()['error'] == 'Paystack is the only supported payment method.'

    monkeypatch.setattr(application, 'is_paystack_configured', lambda: False)
    unavailable = paystack_tour['client'].post(
        '/booking-confirmation', json=_booking_payload(paystack_tour)
    )
    assert unavailable.status_code == 503
    with application.app.app_context():
        assert application.Booking.query.filter_by(tour=paystack_tour['slug']).count() == 0
        assert application.db.session.get(
            application.TourSchedule, paystack_tour['schedule_id']
        ).booked_count == 0


def test_aged_pending_paystack_status_reconciles_success(paystack_tour, monkeypatch):
    result = _start_booking(paystack_tour)
    with application.app.app_context():
        booking = application.Booking.query.filter_by(id=result['booking']['id']).one()
        booking.created_at = datetime.utcnow() - timedelta(minutes=20)
        transaction = _transaction(booking)
        application.db.session.commit()
    verified = []

    def verify(reference):
        verified.append(reference)
        return transaction

    monkeypatch.setattr(application, 'verify_paystack_transaction', verify)
    response = paystack_tour['client'].get(
        f"/api/payment-status/{result['payment_reference']}"
    )

    assert response.status_code == 200
    assert response.get_json()['payment_status'] == 'paid'
    assert verified == [result['booking']['paystack_reference']]


def test_aged_abandoned_paystack_status_releases_capacity(paystack_tour, monkeypatch):
    result = _start_booking(paystack_tour)
    with application.app.app_context():
        booking = application.Booking.query.filter_by(id=result['booking']['id']).one()
        booking.created_at = datetime.utcnow() - timedelta(minutes=20)
        transaction = _transaction(booking, status='abandoned')
        application.db.session.commit()
    monkeypatch.setattr(
        application, 'verify_paystack_transaction', lambda reference: transaction
    )

    response = paystack_tour['client'].get(
        f"/api/payment-status/{result['payment_reference']}"
    )

    assert response.status_code == 200
    assert response.get_json()['payment_status'] == 'failed'
    with application.app.app_context():
        booking = application.Booking.query.filter_by(id=result['booking']['id']).one()
        assert booking.status == 'cancelled'
        assert application.db.session.get(
            application.TourSchedule, paystack_tour['schedule_id']
        ).booked_count == 0


def test_pending_paystack_reconciliation_is_throttled(paystack_tour, monkeypatch):
    result = _start_booking(paystack_tour)
    with application.app.app_context():
        booking = application.Booking.query.filter_by(id=result['booking']['id']).one()
        booking.created_at = datetime.utcnow() - timedelta(minutes=20)
        transaction = _transaction(booking, status='pending')
        application.db.session.commit()
    verified = []

    def verify(reference):
        verified.append(reference)
        return transaction

    monkeypatch.setattr(application, 'verify_paystack_transaction', verify)
    for _ in range(2):
        response = paystack_tour['client'].get(
            f"/api/payment-status/{result['payment_reference']}"
        )
        assert response.status_code == 200
        assert response.get_json()['payment_status'] == 'pending'
    assert verified == [result['booking']['paystack_reference']]


def test_payment_migrations_preserve_historical_mpesa_and_paystack_rows(monkeypatch):
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE booking (
                id INTEGER PRIMARY KEY,
                mpesa_receipt_number VARCHAR(30),
                checkout_request_id VARCHAR(100)
            )
        """))
        connection.execute(text("""
            CREATE TABLE vendor_subscription_payment (
                id INTEGER PRIMARY KEY,
                mpesa_receipt_number VARCHAR(30),
                checkout_request_id VARCHAR(100)
            )
        """))
        for table in ('booking', 'vendor_subscription_payment'):
            connection.execute(text(
                f'INSERT INTO {table} (id, mpesa_receipt_number, checkout_request_id) '
                'VALUES (1, :receipt, NULL), (2, NULL, :checkout), (3, NULL, NULL)'
            ), {'receipt': 'HISTORICAL001', 'checkout': 'ws_CO_historical'})

    monkeypatch.setattr(application, 'db', SimpleNamespace(engine=engine, inspect=inspect))
    application.ensure_booking_payment_columns()
    application.ensure_subscription_payment_columns()

    with engine.begin() as connection:
        for table in ('booking', 'vendor_subscription_payment'):
            assert connection.execute(text(
                f'SELECT id, payment_method FROM {table} ORDER BY id'
            )).all() == [(1, 'mpesa'), (2, 'mpesa'), (3, 'mpesa')]
            connection.execute(text(
                f'INSERT INTO {table} (id, payment_method, paystack_reference) '
                'VALUES (4, :method, :reference)'
            ), {'method': 'paystack', 'reference': 'KB-paystack-historical'})
            # Simulate an earlier migration that defaulted legacy rows to Paystack.
            connection.execute(text(f'UPDATE {table} SET payment_method = :method WHERE id = 3'),
                               {'method': 'paystack'})

    application.ensure_booking_payment_columns()
    application.ensure_subscription_payment_columns()

    with engine.connect() as connection:
        for table in ('booking', 'vendor_subscription_payment'):
            assert connection.execute(text(
                f'SELECT id, payment_method FROM {table} ORDER BY id'
            )).all() == [
                (1, 'mpesa'), (2, 'mpesa'), (3, 'mpesa'), (4, 'paystack'),
            ]
    assert application.Booking.__table__.c.payment_method.default.arg == 'paystack'
    assert application.VendorSubscriptionPayment.__table__.c.payment_method.default.arg == 'paystack'
    engine.dispose()


def test_paystack_unknown_initialization_keeps_the_pending_reference(paystack_tour, monkeypatch):
    def unavailable(**kwargs):
        raise application.PaystackError('Paystack timed out.', outcome_unknown=True)

    monkeypatch.setattr(application, 'initialize_paystack_transaction', unavailable)

    response = paystack_tour['client'].post(
        '/booking-confirmation', json=_booking_payload(paystack_tour)
    )

    assert response.status_code == 202
    result = response.get_json()
    assert result['payment_pending'] is True
    assert 'authorization_url' not in result
    with application.app.app_context():
        booking = application.Booking.query.filter_by(id=result['booking']['id']).one()
        assert booking.paystack_reference
        assert booking.payment_status == 'pending'
        assert application.db.session.get(
            application.TourSchedule, paystack_tour['schedule_id']
        ).booked_count == 1


def test_paystack_callback_verifies_and_issues_a_receipt(paystack_tour, monkeypatch):
    result = _start_booking(paystack_tour)
    verified = []

    def verify(reference):
        verified.append(reference)
        with application.app.app_context():
            booking = application.Booking.query.filter_by(id=result['booking']['id']).one()
            return _transaction(booking)

    monkeypatch.setattr(application, 'verify_paystack_transaction', verify)

    callback = paystack_tour['client'].get(
        '/paystack/callback', query_string={'reference': result['booking']['paystack_reference']}
    )

    assert callback.status_code == 302
    assert '/booking-confirmation.html?' in callback.headers['Location']
    assert 'method=paystack' in callback.headers['Location']
    assert verified == [result['booking']['paystack_reference']]
    with application.app.app_context():
        booking = application.Booking.query.filter_by(id=result['booking']['id']).one()
        assert booking.payment_status == 'paid'
        assert booking.status == 'confirmed'
        assert booking.payment_channel == 'card'
        assert booking.payment_confirmed_at is not None
        assert application.booking_payment_receipt(booking) == booking.paystack_reference

    status = paystack_tour['client'].get(
        f"/api/payment-status/{result['payment_reference']}"
    ).get_json()
    assert status['payment_method'] == 'paystack'
    assert status['payment_receipt'] == result['booking']['paystack_reference']
    receipt = paystack_tour['client'].get(status['document_urls']['receipt'])
    assert receipt.status_code == 200
    assert receipt.data.startswith(b'%PDF-')

    monkeypatch.setattr(
        application, 'verify_paystack_transaction',
        lambda reference: pytest.fail('A duplicate callback must not verify again.'),
    )
    duplicate = paystack_tour['client'].get(
        '/paystack/callback', query_string={'reference': result['booking']['paystack_reference']}
    )
    assert duplicate.status_code == 302


def test_paystack_webhook_requires_a_signature_and_is_idempotent(paystack_tour):
    result = _start_booking(paystack_tour)
    with application.app.app_context():
        booking = application.Booking.query.filter_by(id=result['booking']['id']).one()
        transaction = _transaction(booking)
    payload = {'event': 'charge.success', 'data': transaction}

    unsigned = paystack_tour['client'].post('/paystack/webhook', json=payload)
    assert unsigned.status_code == 401

    accepted = _legacy_webhook(paystack_tour['client'], payload)
    duplicate = _legacy_webhook(paystack_tour['client'], payload)
    assert accepted.status_code == 204
    assert duplicate.status_code == 204
    with application.app.app_context():
        booking = application.Booking.query.filter_by(id=result['booking']['id']).one()
        assert booking.payment_status == 'paid'
        assert application.db.session.get(
            application.TourSchedule, paystack_tour['schedule_id']
        ).booked_count == 1


def test_paystack_webhook_rejects_mismatched_amount_and_currency(paystack_tour):
    result = _start_booking(paystack_tour)
    with application.app.app_context():
        booking = application.Booking.query.filter_by(id=result['booking']['id']).one()
        wrong_amount = _transaction(booking, amount=int(round(booking.amount)) * 100 + 1)
        wrong_currency = _transaction(booking, currency='USD')

    assert _legacy_webhook(paystack_tour['client'], {
        'event': 'charge.success', 'data': wrong_amount,
    }).status_code == 400
    assert _legacy_webhook(paystack_tour['client'], {
        'event': 'charge.success', 'data': wrong_currency,
    }).status_code == 400
    with application.app.app_context():
        booking = application.Booking.query.filter_by(id=result['booking']['id']).one()
        assert booking.payment_status == 'pending'
        assert booking.status == 'requested'


def test_failed_paystack_webhook_releases_reserved_capacity(paystack_tour):
    result = _start_booking(paystack_tour)
    with application.app.app_context():
        booking = application.Booking.query.filter_by(id=result['booking']['id']).one()
        transaction = _transaction(
            booking, status='failed', gateway_response='Card declined'
        )

    response = _legacy_webhook(paystack_tour['client'], {
        'event': 'charge.failed', 'data': transaction,
    })

    assert response.status_code == 204
    with application.app.app_context():
        booking = application.Booking.query.filter_by(id=result['booking']['id']).one()
        assert booking.payment_status == 'failed'
        assert booking.status == 'cancelled'
        assert application.db.session.get(
            application.TourSchedule, paystack_tour['schedule_id']
        ).booked_count == 0
