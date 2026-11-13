from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import uuid

import pytest

import app as application


def kenya_now():
    return datetime.now(ZoneInfo('Africa/Nairobi')).replace(tzinfo=None)


@pytest.fixture
def refund_scene(monkeypatch):
    """A customer, a tour departure far enough ahead, and a bookable stay."""
    email = f'refund-customer-{uuid.uuid4().hex}@example.test'
    tour_slug = f'refund-tour-{uuid.uuid4().hex}'
    property_slug = f'refund-stay-{uuid.uuid4().hex}'
    now = kenya_now()
    far_start = (now + timedelta(days=8)).replace(second=0, microsecond=0)
    near_start = (now + timedelta(hours=12)).replace(second=0, microsecond=0)
    check_in = (now + timedelta(days=10)).date()
    check_out = check_in + timedelta(days=2)

    with application.app.app_context():
        user = application.User(
            name='Refund Customer',
            email=email,
            password_hash=application.generate_password_hash('refund-test-password'),
        )
        tour = application.Tour(
            slug=tour_slug,
            name='Refund Test Island Tour',
            description='A tour used to test cancellations and refunds.',
            duration='Two hours',
            price=2500,
            max_group_size=8,
        )
        listing = application.Property(
            slug=property_slug,
            owner_name='Refund Test Owner',
            owner_email=email,
            name='Refund Test Villa',
            property_type='Villa',
            location='Shela',
            destination='lamu',
            price_per_night=5000,
            guests=2,
            description='A stay used to test cancellations and refunds.',
        )
        application.db.session.add_all([user, tour, listing])
        application.db.session.flush()
        far_slot = application.TourSchedule(tour_slug=tour_slug, starts_at=far_start, capacity=8, booked_count=2)
        near_slot = application.TourSchedule(tour_slug=tour_slug, starts_at=near_start, capacity=4)
        room = application.PropertyRoom(
            property_id=listing.id,
            name='Garden Room',
            guests=2,
            base_rate=5000,
            total_units=1,
        )
        application.db.session.add_all([far_slot, near_slot, room])
        application.db.session.flush()
        for offset in range((check_out - check_in).days):
            application.db.session.add(application.PropertyAvailability(
                room_id=room.id,
                date=check_in + timedelta(days=offset),
                units_available=1,
                reserved_count=1,
            ))
        application.db.session.commit()
        scene = {
            'email': email,
            'user_id': user.id,
            'tour_slug': tour_slug,
            'property_slug': property_slug,
            'property_id': listing.id,
            'room_id': room.id,
            'far_schedule_id': far_slot.id,
            'near_schedule_id': near_slot.id,
            'far_start': far_start,
            'check_in': check_in.isoformat(),
            'check_out': check_out.isoformat(),
        }

    monkeypatch.setattr(application, 'send_email_message', lambda message, **kwargs: True)
    client = application.app.test_client()
    response = client.post('/login', data={'email': email, 'password': 'refund-test-password'})
    assert response.status_code == 302
    with client.session_transaction() as session:
        csrf_token = session['customer_csrf']
    scene['client'] = client
    scene['csrf'] = {'X-CSRF-Token': csrf_token}

    yield scene

    with application.app.app_context():
        application.Booking.query.filter_by(user_id=scene['user_id']).delete(synchronize_session=False)
        application.PropertyAvailability.query.filter_by(room_id=scene['room_id']).delete()
        application.db.session.delete(application.db.session.get(application.PropertyRoom, scene['room_id']))
        application.db.session.delete(application.db.session.get(application.Property, scene['property_id']))
        application.TourSchedule.query.filter_by(tour_slug=scene['tour_slug']).delete()
        application.db.session.delete(application.db.session.get(application.Tour, scene['tour_slug']))
        application.db.session.delete(application.db.session.get(application.User, scene['user_id']))
        application.db.session.commit()


@pytest.fixture
def admin_client():
    email = f'refund-admin-{uuid.uuid4().hex}@example.test'
    with application.app.app_context():
        admin = application.AdminAccount(
            name='Refund test admin',
            email=email,
            password_hash=application.generate_password_hash('refund-admin-password'),
        )
        application.db.session.add(admin)
        application.db.session.commit()
        admin_id = admin.id

    client = application.app.test_client()
    response = client.post('/admin/login', data={'email': email, 'password': 'refund-admin-password'})
    assert response.status_code == 302
    with client.session_transaction() as session:
        csrf_token = session['admin_csrf']

    yield client, {'X-CSRF-Token': csrf_token}

    with application.app.app_context():
        application.AdminAccount.query.filter_by(id=admin_id).delete()
        application.db.session.commit()


def make_tour_booking(scene, *, schedule='far', payment_status='paid', status='confirmed', **overrides):
    with application.app.app_context():
        schedule_id = scene['far_schedule_id'] if schedule == 'far' else scene['near_schedule_id']
        slot = application.db.session.get(application.TourSchedule, schedule_id)
        values = {
            'user_id': scene['user_id'],
            'schedule_id': slot.id,
            'name': 'Refund Customer',
            'email': scene['email'],
            'phone': '+254712345678',
            'tour': scene['tour_slug'],
            'date': slot.starts_at.date().isoformat(),
            'time': slot.starts_at.strftime('%H:%M'),
            'guests': 2,
            'amount': 5000,
            'commission_rate': 15,
            'payment_status': payment_status,
            'status': status,
        }
        values.update(overrides)
        booking = application.Booking(**values)
        application.db.session.add(booking)
        application.db.session.commit()
        return booking.id


def make_stay_booking(scene, *, payment_status='paid', status='confirmed', **overrides):
    with application.app.app_context():
        values = {
            'user_id': scene['user_id'],
            'booking_type': 'property',
            'property_id': scene['property_id'],
            'room_id': scene['room_id'],
            'tour': scene['property_slug'],
            'check_in': scene['check_in'],
            'check_out': scene['check_out'],
            'nights': 2,
            'date': scene['check_in'],
            'time': '',
            'name': 'Refund Customer',
            'email': scene['email'],
            'phone': '+254712345678',
            'guests': 2,
            'amount': 10000,
            'commission_rate': 15,
            'payment_status': payment_status,
            'status': status,
        }
        values.update(overrides)
        booking = application.Booking(**values)
        application.db.session.add(booking)
        application.db.session.commit()
        return booking.id


def read_booking(booking_id):
    with application.app.app_context():
        return application.db.session.get(application.Booking, booking_id).to_dict()


def reserved_nights(scene):
    with application.app.app_context():
        rows = application.PropertyAvailability.query.filter_by(room_id=scene['room_id']).all()
        return [row.reserved_count for row in rows]


def test_customer_cancellation_queues_full_refund_for_a_tour(refund_scene):
    booking_id = make_tour_booking(refund_scene)

    response = refund_scene['client'].post(
        f'/api/customer/bookings/{booking_id}/cancel',
        headers=refund_scene['csrf'],
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['refund_queued'] is True
    booking = payload['booking']
    assert booking['status'] == 'cancelled'
    assert booking['payment_status'] == 'paid'
    assert booking['refund_status'] == 'pending'
    assert booking['refund_amount'] == 5000
    assert 'customer' in booking['refund_reason']
    assert booking['refund_requested_at']
    assert booking['refund_paid_at'] is None

    with application.app.app_context():
        slot = application.db.session.get(application.TourSchedule, refund_scene['far_schedule_id'])
        assert slot.booked_count == 0

    listed = next(
        row for row in refund_scene['client'].get('/api/customer/bookings').get_json()['bookings']
        if row['id'] == booking_id
    )
    assert listed['refund_status'] == 'pending'
    assert listed['refund_amount'] == 5000


def test_customer_cancellation_inside_the_cutoff_is_blocked(refund_scene):
    booking_id = make_tour_booking(refund_scene, schedule='near')

    response = refund_scene['client'].post(
        f'/api/customer/bookings/{booking_id}/cancel',
        headers=refund_scene['csrf'],
    )

    assert response.status_code == 400
    assert '48 hours' in response.get_json()['error']
    booking = read_booking(booking_id)
    assert booking['status'] == 'confirmed'
    assert booking['refund_status'] == 'none'
    assert booking['refund_amount'] == 0


def test_cancelling_an_unpaid_booking_queues_no_refund(refund_scene):
    booking_id = make_tour_booking(refund_scene, payment_status='failed')

    response = refund_scene['client'].post(
        f'/api/customer/bookings/{booking_id}/cancel',
        headers=refund_scene['csrf'],
    )

    assert response.status_code == 200
    assert response.get_json()['refund_queued'] is False
    booking = read_booking(booking_id)
    assert booking['status'] == 'cancelled'
    assert booking['refund_status'] == 'none'
    assert booking['refund_amount'] == 0


def test_stay_cancellation_releases_nights_and_queues_refund(refund_scene):
    booking_id = make_stay_booking(refund_scene)
    assert reserved_nights(refund_scene) == [1, 1]

    response = refund_scene['client'].post(
        f'/api/customer/bookings/{booking_id}/cancel',
        headers=refund_scene['csrf'],
    )

    assert response.status_code == 200
    payload = response.get_json()['booking']
    assert payload['status'] == 'cancelled'
    assert payload['refund_status'] == 'pending'
    assert payload['refund_amount'] == 10000
    assert reserved_nights(refund_scene) == [0, 0]


def test_admin_cancellation_releases_the_stay_and_queues_a_refund(refund_scene, admin_client):
    admin, headers = admin_client
    booking_id = make_stay_booking(refund_scene)

    response = admin.post(f'/api/admin/bookings/{booking_id}/cancel', headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['refund_queued'] is True
    assert payload['booking']['status'] == 'cancelled'
    assert payload['booking']['refund_status'] == 'pending'
    assert 'administrator' in payload['booking']['refund_reason']
    assert reserved_nights(refund_scene) == [0, 0]

    operations = admin.get('/api/admin/operations').get_json()
    assert operations['refunds_due'] == {'count': 1, 'amount': 10000}


def test_admin_refund_requires_a_paid_booking(refund_scene, admin_client):
    admin, headers = admin_client
    booking_id = make_tour_booking(refund_scene, payment_status='failed', status='cancelled')

    response = admin.post(
        f'/api/admin/bookings/{booking_id}/refund',
        json={'status': 'pending'},
        headers=headers,
    )

    assert response.status_code == 409
    assert 'Only paid bookings' in response.get_json()['error']


def test_admin_can_reject_and_reopen_a_refund(refund_scene, admin_client):
    admin, headers = admin_client
    booking_id = make_tour_booking(refund_scene, status='cancelled', refund_status='pending', refund_amount=5000)

    rejected = admin.post(
        f'/api/admin/bookings/{booking_id}/refund',
        json={'status': 'rejected'},
        headers=headers,
    )
    assert rejected.status_code == 200
    assert rejected.get_json()['booking']['refund_status'] == 'rejected'
    assert rejected.get_json()['booking']['payment_status'] == 'paid'

    reopened = admin.post(
        f'/api/admin/bookings/{booking_id}/refund',
        json={'status': 'pending', 'reason': 'Reviewing the declined refund again.'},
        headers=headers,
    )
    assert reopened.status_code == 200
    assert reopened.get_json()['booking']['refund_status'] == 'pending'
    assert reopened.get_json()['booking']['refund_reason'] == 'Reviewing the declined refund again.'


def test_a_paid_refund_cannot_be_paid_twice(refund_scene, admin_client):
    admin, headers = admin_client
    booking_id = make_tour_booking(refund_scene, status='cancelled', refund_status='pending', refund_amount=5000)

    first = admin.post(
        f'/api/admin/bookings/{booking_id}/refund',
        json={'status': 'paid'},
        headers=headers,
    )
    assert first.status_code == 200
    assert first.get_json()['booking']['payment_status'] == 'refunded'
    assert first.get_json()['booking']['refund_paid_at']

    second = admin.post(
        f'/api/admin/bookings/{booking_id}/refund',
        json={'status': 'paid'},
        headers=headers,
    )
    assert second.status_code == 409


def test_late_mpesa_payment_on_a_cancelled_booking_queues_a_refund(refund_scene, monkeypatch):
    booking_id = make_tour_booking(
        refund_scene,
        schedule='near',
        payment_status='pending',
        status='cancelled',
        checkout_request_id='ws_CO_late_refund',
        merchant_request_id='merchant_late_refund',
    )

    monkeypatch.setattr(application, 'query_stk_push', lambda checkout_id: {
        'ResponseCode': '0',
        'ResultCode': 0,
        'ResultDesc': 'The service request is processed successfully.',
        'CheckoutRequestID': checkout_id,
    })

    response = refund_scene['client'].post('/daraja/callback', json={
        'Body': {
            'stkCallback': {
                'MerchantRequestID': 'merchant_late_refund',
                'CheckoutRequestID': 'ws_CO_late_refund',
                'ResultCode': 0,
                'ResultDesc': 'The service request is processed successfully.',
                'CallbackMetadata': {
                    'Item': [
                        {'Name': 'Amount', 'Value': 5000},
                        {'Name': 'MpesaReceiptNumber', 'Value': 'QAB123XYZ'},
                        {'Name': 'PhoneNumber', 'Value': 254712345678},
                    ],
                },
            },
        },
    })

    assert response.status_code == 204
    booking = read_booking(booking_id)
    assert booking['status'] == 'cancelled'
    assert booking['payment_status'] == 'paid'
    assert booking['refund_status'] == 'pending'
    assert booking['refund_amount'] == 5000
    assert booking['mpesa_receipt_number'] == 'QAB123XYZ'


def test_cancel_requires_csrf(refund_scene):
    booking_id = make_tour_booking(refund_scene)

    response = refund_scene['client'].post(f'/api/customer/bookings/{booking_id}/cancel')

    assert response.status_code == 403
    assert read_booking(booking_id)['status'] == 'confirmed'
