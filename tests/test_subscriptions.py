"""Monthly partner subscriptions and the lower commission they unlock."""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

import app as application

KENYA_TIMEZONE = ZoneInfo('Africa/Nairobi')


def _future_start(days=8):
    return (
        datetime.now(KENYA_TIMEZONE).replace(tzinfo=None) + timedelta(days=days)
    ).replace(second=0, microsecond=0)


def _subscribe(vendor_id, days=10, business_types='tours'):
    with application.app.app_context():
        vendor = application.db.session.get(application.VendorAccount, vendor_id)
        vendor.business_types = business_types
        vendor.subscription_status = 'active'
        vendor.subscription_plan = 'monthly'
        vendor.subscription_started_at = datetime.utcnow() - timedelta(days=5)
        vendor.subscription_renews_at = datetime.utcnow() + timedelta(days=days)
        vendor.subscription_monthly_fee = 2500.0
        application.db.session.commit()


@pytest.fixture
def operator(monkeypatch):
    """A tour operator with one bookable departure, plus its signed-in portal."""
    monkeypatch.setattr(application, 'is_paystack_configured', lambda: True)
    monkeypatch.setattr(application, 'send_booking_confirmation', lambda booking, **kwargs: True)
    monkeypatch.setattr(application, 'send_booking_status_notification', lambda booking, **kwargs: True)
    monkeypatch.setattr(application, 'initialize_paystack_transaction', lambda **kwargs: {
        'reference': kwargs['reference'],
        'authorization_url': 'https://checkout.paystack.com/subscription-test',
        'access_code': 'access_test',
        'customer_message': 'Continue to Paystack.',
    })

    email = f'subscription-vendor-{uuid.uuid4().hex}@example.test'
    slug = f'subscription-tour-{uuid.uuid4().hex}'
    with application.app.app_context():
        vendor = application.VendorAccount(
            name='Subscription Safari',
            email=email,
            password_hash=application.generate_password_hash('test-vendor-password'),
            business_types='tours',
            phone='+254712345678',
        )
        application.db.session.add(vendor)
        application.db.session.flush()
        tour = application.Tour(
            slug=slug,
            vendor_id=vendor.id,
            name='Subscription Dhow Day',
            description='A tour used to test subscriber pricing.',
            duration='Half day',
            price=2500,
            category='Dhow & Island Hopping',
            min_group_size=1,
            max_group_size=6,
        )
        application.db.session.add(tour)
        application.db.session.flush()
        schedule = application.TourSchedule(
            tour_slug=slug, starts_at=_future_start(), capacity=8
        )
        application.db.session.add(schedule)
        application.db.session.commit()
        vendor_id = vendor.id
        schedule_id = schedule.id
        starts_at = schedule.starts_at

    client = application.app.test_client()
    response = client.post('/vendor/login', data={
        'email': email,
        'password': 'test-vendor-password',
    })
    assert response.status_code == 302
    with client.session_transaction() as session:
        csrf_token = session['vendor_csrf']

    yield {
        'client': client,
        'headers': {'X-CSRF-Token': csrf_token},
        'vendor_id': vendor_id,
        'slug': slug,
        'schedule_id': schedule_id,
        'starts_at': starts_at,
    }

    with application.app.app_context():
        booking_ids = [
            booking_id
            for (booking_id,) in application.db.session.query(application.Booking.id)
            .filter_by(tour=slug)
            .all()
        ]
        if booking_ids:
            application.BookingDispute.query.filter(
                application.BookingDispute.booking_id.in_(booking_ids)
            ).delete(synchronize_session=False)
        application.Booking.query.filter_by(tour=slug).delete()
        application.TourSchedule.query.filter_by(tour_slug=slug).delete()
        application.Tour.query.filter_by(slug=slug).delete()
        application.VendorSubscriptionPayment.query.filter_by(vendor_id=vendor_id).delete()
        application.db.session.delete(application.db.session.get(application.VendorAccount, vendor_id))
        application.db.session.commit()


@pytest.fixture
def guest_client():
    email = f'subscription-guest-{uuid.uuid4().hex}@example.test'
    with application.app.app_context():
        user = application.User(
            name='Subscription Guest',
            email=email,
            password_hash=application.generate_password_hash('guest-test-password'),
        )
        application.db.session.add(user)
        application.db.session.commit()
        user_id = user.id

    client = application.app.test_client()
    response = client.post('/login', data={'email': email, 'password': 'guest-test-password'})
    assert response.status_code == 302

    yield {'client': client, 'email': email, 'user_id': user_id}

    with application.app.app_context():
        application.Booking.query.filter_by(user_id=user_id).delete()
        user = application.db.session.get(application.User, user_id)
        if user:
            application.db.session.delete(user)
        application.db.session.commit()


@pytest.fixture
def admin_client():
    email = f'subscription-admin-{uuid.uuid4().hex}@example.test'
    with application.app.app_context():
        admin = application.AdminAccount(
            name='Subscription test',
            email=email,
            password_hash=application.generate_password_hash('test-admin-password'),
        )
        application.db.session.add(admin)
        application.db.session.commit()
        admin_id = admin.id

    client = application.app.test_client()
    response = client.post('/admin/login', data={'email': email, 'password': 'test-admin-password'})
    assert response.status_code == 302
    with client.session_transaction() as session:
        csrf_token = session['admin_csrf']

    yield client, {'X-CSRF-Token': csrf_token}

    with application.app.app_context():
        application.AdminAccount.query.filter_by(id=admin_id).delete()
        application.db.session.commit()


def book_tour(operator, guest, guests=2):
    response = guest['client'].post('/booking-confirmation', json={
        'name': 'Subscription Guest',
        'email': guest['email'],
        'contact_phone': '+254 712 345 678',
        'tour': operator['slug'],
        'schedule_id': operator['schedule_id'],
        'guests': guests,
        'date': 'ignored-for-scheduled-tour',
        'time': 'ignored-for-scheduled-tour',
        'message': '',
    })
    assert response.status_code == 201, response.get_json()
    return response.get_json()['booking']


def test_unsubscribed_operator_pays_the_standard_commission(operator, guest_client):
    booking = book_tour(operator, guest_client)

    assert booking['subtotal_amount'] == 5000
    assert booking['host_commission_rate'] == 4
    assert booking['host_commission_amount'] == 200
    assert booking['host_payout_amount'] == 4800
    # Guest fees are the same whoever owns the listing.
    assert booking['service_fee_amount'] == 450
    assert booking['booking_fee_amount'] == 100
    assert booking['amount'] == 5550


def test_active_subscription_charges_the_lower_commission(operator, guest_client):
    _subscribe(operator['vendor_id'])

    booking = book_tour(operator, guest_client)

    assert booking['host_commission_rate'] == 2.5
    assert booking['host_commission_amount'] == 125
    assert booking['host_payout_amount'] == 4875
    assert booking['subtotal_amount'] == 5000
    assert booking['amount'] == 5550


def test_expired_subscription_falls_back_to_the_standard_commission(operator, guest_client):
    _subscribe(operator['vendor_id'], days=-1)

    booking = book_tour(operator, guest_client)

    assert booking['host_commission_rate'] == 4
    assert booking['host_commission_amount'] == 200


def test_only_tour_and_safari_operators_get_the_subscriber_rate(operator):
    with application.app.app_context():
        _subscribe(operator['vendor_id'], business_types='accommodation')
        assert application.vendor_has_operator_subscription(operator['vendor_id']) is False
        quote = application.booking_fee_quote(5000, operator['vendor_id'])
        assert quote['host_commission_rate'] == 4.0
        assert quote['host_commission'] == 200


def test_vendor_renews_with_paystack_and_the_lower_rate_applies(operator, monkeypatch, admin_client):
    with application.app.app_context():
        assert application.vendor_has_operator_subscription(operator['vendor_id']) is False

    response = operator['client'].post(
        '/api/vendor/subscription/renew',
        json={'payment_method': 'paystack'},
        headers=operator['headers'],
    )
    assert response.status_code == 202, response.get_json()
    result = response.get_json()
    reference = result['payment_reference']
    assert result['authorization_url'] == 'https://checkout.paystack.com/subscription-test'

    with application.app.app_context():
        payment = application.VendorSubscriptionPayment.query.filter_by(
            vendor_id=operator['vendor_id']
        ).one()
        assert payment.status == 'pending'
        assert payment.payment_method == 'paystack'
        assert payment.amount == 2500
        assert payment.paystack_reference
        assert application.db.session.get(
            application.VendorAccount, operator['vendor_id']
        ).subscription_status == 'inactive'
        transaction = {
            'reference': payment.paystack_reference,
            'status': 'success',
            'currency': 'KES',
            'amount': int(round(payment.amount)) * 100,
            'channel': 'card',
        }
        paystack_reference = payment.paystack_reference
    monkeypatch.setattr(application, 'verify_paystack_transaction', lambda reference: transaction)

    callback = operator['client'].get(
        '/paystack/callback', query_string={'reference': paystack_reference}
    )
    assert callback.status_code == 302
    assert callback.headers['Location'].startswith('/partner/dashboard?')

    with application.app.app_context():
        payment = application.VendorSubscriptionPayment.query.filter_by(
            vendor_id=operator['vendor_id']
        ).one()
        assert payment.status == 'paid'
        assert payment.payment_channel == 'card'
        assert payment.period_start is not None
        assert (payment.period_end - payment.period_start) == timedelta(days=30)

        vendor = application.db.session.get(application.VendorAccount, operator['vendor_id'])
        assert vendor.subscription_is_active() is True
        assert vendor.subscription_plan == 'monthly'
        assert vendor.subscription_monthly_fee == 2500
        assert vendor.subscription_renews_at == payment.period_end
        assert application.vendor_has_operator_subscription(operator['vendor_id']) is True

    portal = operator['client'].get('/api/vendor/catalogue')
    assert portal.status_code == 200
    subscription = portal.get_json()['subscription']
    assert subscription['is_active'] is True
    assert subscription['eligible'] is True
    assert subscription['host_commission_rate'] == 2.5
    assert subscription['monthly_fee'] == 2500.0
    assert subscription['payment_methods'] == {'paystack': True}
    assert subscription['payments'][0]['reference'] == reference
    assert subscription['payments'][0]['status'] == 'paid'
    assert subscription['payments'][0]['payment_method'] == 'paystack'

    admin, admin_headers = admin_client
    operations = admin.get('/api/admin/operations').get_json()
    assert operations['analytics']['subscription_revenue'] >= 2500
    assert operations['analytics']['active_subscriptions'] >= 1


def test_subscription_renewal_rejects_mpesa_and_missing_configuration(operator, monkeypatch):
    invalid = operator['client'].post(
        '/api/vendor/subscription/renew',
        json={'payment_method': 'mpesa'},
        headers=operator['headers'],
    )
    assert invalid.status_code == 400
    assert invalid.get_json()['error'] == 'Paystack is the only supported payment method.'

    monkeypatch.setattr(application, 'is_paystack_configured', lambda: False)
    unavailable = operator['client'].post(
        '/api/vendor/subscription/renew',
        json={'payment_method': 'paystack'},
        headers=operator['headers'],
    )
    assert unavailable.status_code == 503
    with application.app.app_context():
        assert application.VendorSubscriptionPayment.query.filter_by(
            vendor_id=operator['vendor_id']
        ).count() == 0


def test_renewal_rejects_non_operators_and_missing_csrf(operator):
    _subscribe(operator['vendor_id'], business_types='accommodation')
    response = operator['client'].post(
        '/api/vendor/subscription/renew',
        json={'payment_method': 'paystack'},
        headers=operator['headers'],
    )
    assert response.status_code == 400
    assert 'tour and safari operators' in response.get_json()['error']

    with application.app.app_context():
        vendor = application.db.session.get(application.VendorAccount, operator['vendor_id'])
        vendor.business_types = 'tours'
        application.db.session.commit()
    response = operator['client'].post(
        '/api/vendor/subscription/renew',
        json={'payment_method': 'paystack'},
    )
    assert response.status_code == 403

    with application.app.app_context():
        assert application.VendorSubscriptionPayment.query.filter_by(
            vendor_id=operator['vendor_id']
        ).count() == 0


def test_subscription_webhook_rejects_a_mismatched_amount(operator, monkeypatch):
    operator['client'].post(
        '/api/vendor/subscription/renew',
        json={'payment_method': 'paystack'},
        headers=operator['headers'],
    )
    with application.app.app_context():
        payment = application.VendorSubscriptionPayment.query.filter_by(
            vendor_id=operator['vendor_id']
        ).one()
        transaction = {
            'reference': payment.paystack_reference,
            'status': 'success',
            'currency': 'KES',
            'amount': 10000,
            'channel': 'card',
        }

    raw_body = json.dumps(
        {'event': 'charge.success', 'data': transaction}, separators=(',', ':')
    ).encode()
    signature = hmac.new(
        b'sk_test_subscription_secret', raw_body, hashlib.sha512
    ).hexdigest()
    monkeypatch.setenv('PAYSTACK_SECRET_KEY', 'sk_test_subscription_secret')
    response = application.app.test_client().post(
        '/paystack/webhook',
        data=raw_body,
        content_type='application/json',
        headers={'x-paystack-signature': signature},
    )
    assert response.status_code == 400

    with application.app.app_context():
        payment = application.VendorSubscriptionPayment.query.filter_by(
            vendor_id=operator['vendor_id']
        ).one()
        assert payment.status == 'pending'
        assert application.vendor_has_operator_subscription(operator['vendor_id']) is False


def test_admin_can_comp_and_end_a_subscription(operator, admin_client):
    admin, headers = admin_client

    response = admin.post(
        f"/api/admin/vendors/{operator['vendor_id']}/subscription",
        json={'action': 'activate', 'months': 1},
        headers=headers,
    )
    assert response.status_code == 200
    subscription = response.get_json()['vendor']['subscription']
    assert subscription['is_active'] is True
    assert subscription['plan'] == 'complimentary'
    with application.app.app_context():
        quote = application.booking_fee_quote(5000, operator['vendor_id'])
        assert quote['host_commission_rate'] == 2.5
        assert quote['host_commission'] == 125

    response = admin.post(
        f"/api/admin/vendors/{operator['vendor_id']}/subscription",
        json={'action': 'end'},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.get_json()['vendor']['subscription']['is_active'] is False
    with application.app.app_context():
        quote = application.booking_fee_quote(5000, operator['vendor_id'])
        assert quote['host_commission_rate'] == 4.0
        assert quote['host_commission'] == 200

    assert admin.post(
        f"/api/admin/vendors/{operator['vendor_id']}/subscription",
        json={'action': 'activate', 'months': 13},
        headers=headers,
    ).status_code == 400
    assert admin.post(
        f"/api/admin/vendors/{operator['vendor_id']}/subscription",
        json={'action': 'pause'},
        headers=headers,
    ).status_code == 400


def test_vendor_renews_with_paystack_and_duplicate_webhooks_do_not_extend_twice(operator, monkeypatch):
    monkeypatch.setattr(application, 'is_paystack_configured', lambda: True)
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        return {
            'reference': kwargs['reference'],
            'authorization_url': 'https://checkout.paystack.com/subscription-test',
            'access_code': 'access_test',
            'customer_message': 'Continue to Paystack.',
        }

    monkeypatch.setattr(application, 'initialize_paystack_transaction', initialize)
    response = operator['client'].post(
        '/api/vendor/subscription/renew',
        json={'payment_method': 'paystack'},
        headers=operator['headers'],
    )
    assert response.status_code == 202, response.get_json()
    result = response.get_json()
    assert result['authorization_url'] == 'https://checkout.paystack.com/subscription-test'

    with application.app.app_context():
        payment = application.VendorSubscriptionPayment.query.filter_by(
            vendor_id=operator['vendor_id']
        ).one()
        assert payment.payment_method == 'paystack'
        assert payment.paystack_reference == captured['reference']
        assert payment.status == 'pending'
        assert captured['email'] == application.db.session.get(
            application.VendorAccount, operator['vendor_id']
        ).email
        transaction = {
            'reference': payment.paystack_reference,
            'status': 'success',
            'currency': 'KES',
            'amount': int(round(payment.amount)) * 100,
            'channel': 'bank_transfer',
        }
        payment_reference = payment.reference

    raw_body = json.dumps(
        {'event': 'charge.success', 'data': transaction}, separators=(',', ':')
    ).encode()
    signature = hmac.new(
        b'sk_test_subscription_secret', raw_body, hashlib.sha512
    ).hexdigest()
    monkeypatch.setenv('PAYSTACK_SECRET_KEY', 'sk_test_subscription_secret')
    webhook_client = application.app.test_client()
    for _ in range(2):
        webhook = webhook_client.post(
            '/paystack/webhook',
            data=raw_body,
            content_type='application/json',
            headers={'x-paystack-signature': signature},
        )
        assert webhook.status_code == 204

    with application.app.app_context():
        payment = application.VendorSubscriptionPayment.query.filter_by(
            reference=payment_reference
        ).one()
        assert payment.status == 'paid'
        assert payment.payment_channel == 'bank_transfer'
        assert (payment.period_end - payment.period_start) == timedelta(days=30)
        period_end = payment.period_end
        vendor = application.db.session.get(application.VendorAccount, operator['vendor_id'])
        assert vendor.subscription_is_active() is True
        assert vendor.subscription_renews_at == period_end

    status = operator['client'].get(
        f'/api/vendor/subscription/status/{payment_reference}'
    )
    assert status.status_code == 200
    assert status.get_json()['payment']['payment_method'] == 'paystack'
    assert status.get_json()['subscription']['payment_methods']['paystack'] is True


def test_subscription_status_reconciles_an_aged_pending_payment(operator, monkeypatch):
    response = operator['client'].post(
        '/api/vendor/subscription/renew',
        json={'payment_method': 'paystack'},
        headers=operator['headers'],
    )
    assert response.status_code == 202, response.get_json()
    payment_reference = response.get_json()['payment_reference']
    with application.app.app_context():
        payment = application.VendorSubscriptionPayment.query.filter_by(
            reference=payment_reference
        ).one()
        payment.created_at = datetime.utcnow() - timedelta(minutes=20)
        transaction = {
            'reference': payment.paystack_reference,
            'status': 'success',
            'currency': 'KES',
            'amount': int(round(payment.amount)) * 100,
            'channel': 'card',
        }
        application.db.session.commit()
    monkeypatch.setattr(
        application, 'verify_paystack_transaction', lambda reference: transaction
    )

    status = operator['client'].get(
        f'/api/vendor/subscription/status/{payment_reference}'
    )

    assert status.status_code == 200
    assert status.get_json()['payment']['status'] == 'paid'
    assert status.get_json()['subscription']['is_active'] is True


def test_renewal_reconciles_an_aged_failed_payment_before_blocking(operator, monkeypatch):
    first = operator['client'].post(
        '/api/vendor/subscription/renew',
        json={'payment_method': 'paystack'},
        headers=operator['headers'],
    )
    assert first.status_code == 202, first.get_json()
    with application.app.app_context():
        payment = application.VendorSubscriptionPayment.query.filter_by(
            reference=first.get_json()['payment_reference']
        ).one()
        payment.created_at = datetime.utcnow() - timedelta(minutes=20)
        transaction = {
            'reference': payment.paystack_reference,
            'status': 'failed',
            'currency': 'KES',
            'amount': int(round(payment.amount)) * 100,
            'channel': 'card',
        }
        first_id = payment.id
        application.db.session.commit()
    verified = []

    def verify(reference):
        verified.append(reference)
        return transaction

    monkeypatch.setattr(application, 'verify_paystack_transaction', verify)
    second = operator['client'].post(
        '/api/vendor/subscription/renew',
        json={'payment_method': 'paystack'},
        headers=operator['headers'],
    )

    assert second.status_code == 202, second.get_json()
    assert verified == [transaction['reference']]
    with application.app.app_context():
        payments = application.VendorSubscriptionPayment.query.filter_by(
            vendor_id=operator['vendor_id']
        ).order_by(application.VendorSubscriptionPayment.id).all()
        assert [(payment.id, payment.status) for payment in payments] == [
            (first_id, 'failed'), (payments[1].id, 'pending'),
        ]
