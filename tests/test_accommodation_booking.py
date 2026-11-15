"""Room inventory, nightly availability and accommodation bookings."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import uuid

import pytest

import app as application

KENYA_TIMEZONE = ZoneInfo('Africa/Nairobi')


def _token():
    return uuid.uuid4().hex[:10]


def stay_dates(start_offset=10, nights=2):
    """Return ISO check-in/check-out dates that are always in the future."""
    check_in = datetime.now(KENYA_TIMEZONE).date() + timedelta(days=start_offset)
    return check_in.isoformat(), (check_in + timedelta(days=nights)).isoformat()


def night_keys(check_in, check_out):
    start = datetime.strptime(check_in, '%Y-%m-%d').date()
    end = datetime.strptime(check_out, '%Y-%m-%d').date()
    return [(start + timedelta(days=offset)).isoformat() for offset in range((end - start).days)]


def reserved_nights(room_id, check_in, check_out):
    """Map each night of the stay to the units currently held for it."""
    keys = night_keys(check_in, check_out)
    rows = application.PropertyAvailability.query.filter(
        application.PropertyAvailability.room_id == room_id,
        application.PropertyAvailability.date.in_([date.fromisoformat(key) for key in keys]),
    ).all()
    counts = {row.date.isoformat(): int(row.reserved_count or 0) for row in rows}
    return {key: counts.get(key, 0) for key in keys}


def _cleanup_property(listing):
    """Delete a listing with its rooms, calendar rows and stay bookings."""
    room_ids = [
        room.id for room in application.PropertyRoom.query.filter_by(property_id=listing.id).all()
    ]
    if room_ids:
        application.PropertyAvailability.query.filter(
            application.PropertyAvailability.room_id.in_(room_ids)
        ).delete(synchronize_session=False)
    application.Booking.query.filter_by(
        tour=listing.slug, booking_type='property'
    ).delete(synchronize_session=False)
    application.Review.query.filter_by(target_type='property', target_id=listing.slug).delete()
    application.PropertyRoom.query.filter_by(property_id=listing.id).delete(synchronize_session=False)
    application.db.session.flush()
    application.db.session.delete(listing)


@pytest.fixture
def admin_client():
    email = f'accommodation-admin-{uuid.uuid4().hex}@example.test'
    with application.app.app_context():
        admin = application.AdminAccount(
            name='Accommodation test',
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


@pytest.fixture
def vendor_pair():
    accounts = []
    with application.app.app_context():
        for label in ('owner', 'other'):
            email = f'accommodation-vendor-{label}-{uuid.uuid4().hex}@example.test'
            vendor = application.VendorAccount(
                name=f'Accommodation Vendor {label}',
                email=email,
                password_hash=application.generate_password_hash('test-vendor-password'),
            )
            application.db.session.add(vendor)
            accounts.append((email, vendor))
        application.db.session.commit()
        vendor_accounts = [(email, vendor.id) for email, vendor in accounts]
        vendor_ids = [vendor_id for _, vendor_id in vendor_accounts]

    clients = []
    for email, vendor_id in vendor_accounts:
        client = application.app.test_client()
        response = client.post('/vendor/login', data={
            'email': email,
            'password': 'test-vendor-password',
        })
        assert response.status_code == 302
        with client.session_transaction() as session:
            csrf_token = session['vendor_csrf']
        clients.append((client, {'X-CSRF-Token': csrf_token}, vendor_id))
    yield clients

    with application.app.app_context():
        for vendor_id in vendor_ids:
            for tour in application.Tour.query.filter_by(vendor_id=vendor_id).all():
                booking_ids = [
                    booking_id for (booking_id,) in application.db.session.query(
                        application.Booking.id
                    ).filter_by(tour=tour.slug).all()
                ]
                if booking_ids:
                    application.BookingDispute.query.filter(
                        application.BookingDispute.booking_id.in_(booking_ids)
                    ).delete(synchronize_session=False)
                application.Booking.query.filter_by(tour=tour.slug).delete()
                application.TourSchedule.query.filter_by(tour_slug=tour.slug).delete()
                application.Review.query.filter_by(target_type='tour', target_id=tour.slug).delete()
                application.db.session.delete(tour)
            for listing in application.Property.query.filter_by(vendor_id=vendor_id).all():
                _cleanup_property(listing)
            vendor = application.db.session.get(application.VendorAccount, vendor_id)
            if vendor:
                application.db.session.delete(vendor)
        application.db.session.commit()


@pytest.fixture
def guest_client():
    email = f'accommodation-guest-{uuid.uuid4().hex}@example.test'
    with application.app.app_context():
        user = application.User(
            name='Accommodation Guest',
            email=email,
            password_hash=application.generate_password_hash('guest-test-password'),
        )
        application.db.session.add(user)
        application.db.session.commit()
        user_id = user.id

    client = application.app.test_client()
    response = client.post('/login', data={'email': email, 'password': 'guest-test-password'})
    assert response.status_code == 302
    with client.session_transaction() as session:
        csrf_token = session['customer_csrf']

    yield {'client': client, 'csrf': csrf_token, 'email': email, 'user_id': user_id}

    with application.app.app_context():
        application.Booking.query.filter_by(user_id=user_id).delete()
        user = application.db.session.get(application.User, user_id)
        if user:
            application.db.session.delete(user)
        application.db.session.commit()


@pytest.fixture
def stay(vendor_pair, guest_client, monkeypatch):
    """A vendor-owned property with a two-unit and a one-unit room."""
    monkeypatch.setattr(application, 'is_daraja_configured', lambda: True)
    monkeypatch.setattr(application, 'send_booking_confirmation', lambda booking, **kwargs: True)
    monkeypatch.setattr(application, 'send_booking_status_notification', lambda booking, **kwargs: True)
    monkeypatch.setattr(application, 'initiate_stk_push', lambda phone, amount, booking_id: {
        'checkout_request_id': f'ws_CO_{booking_id}',
        'merchant_request_id': f'merchant_{booking_id}',
        'customer_message': 'STK prompt sent.',
    })

    owner, owner_headers, owner_id = vendor_pair[0]
    other, other_headers, other_id = vendor_pair[1]
    listing = create_property(owner, owner_headers)
    double = create_room(owner, owner_headers, listing['id'], {
        'name': 'Garden double',
        'guests': 3,
        'base_rate': 8000,
        'total_units': 2,
    })
    single = create_room(owner, owner_headers, listing['id'], {
        'name': 'Single nest',
        'guests': 2,
        'base_rate': 5000,
        'total_units': 1,
    })
    return {
        'property': listing,
        'slug': listing['slug'],
        'rooms': {'double': double, 'single': single},
        'owner': owner,
        'owner_headers': owner_headers,
        'owner_id': owner_id,
        'other': {'client': other, 'headers': other_headers, 'id': other_id},
        'guest': guest_client,
    }


def create_property(client, headers, **overrides):
    payload = {
        'name': f'Test Apartment {_token()}',
        'property_type': 'apartment',
        'location': 'Lamu',
        'price_per_night': 8000,
        'guests': 3,
        'description': 'A listing created for accommodation booking tests.',
        'amenities': ['Wi-Fi', 'Breakfast'],
    }
    payload.update(overrides)
    response = client.post('/api/vendor/properties', json=payload, headers=headers)
    assert response.status_code == 201, response.get_json()
    return response.get_json()['property']


def create_room(client, headers, property_id, overrides=None):
    payload = {
        'name': 'Sea view room',
        'description': 'A room created for accommodation booking tests.',
        'guests': 2,
        'base_rate': 7500,
        'total_units': 1,
    }
    payload.update(overrides or {})
    response = client.post(
        f'/api/vendor/properties/{property_id}/rooms', json=payload, headers=headers
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()['room']


def stay_booking_payload(stay, room, check_in=None, check_out=None, guests=2, **overrides):
    if check_in is None:
        check_in, check_out = stay_dates()
    payload = {
        'name': 'Accommodation Guest',
        'email': stay['guest']['email'],
        'country_code': '+254',
        'phone': '712345678',
        'tour': stay['slug'],
        'booking_type': 'property',
        'room_id': room['id'],
        'check_in': check_in,
        'check_out': check_out,
        'guests': guests,
        'date': check_in,
        'time': '',
        'message': '',
    }
    payload.update(overrides)
    return payload


def _daraja_callback(booking, result_code, metadata=None):
    callback = {
        'MerchantRequestID': booking.merchant_request_id,
        'CheckoutRequestID': booking.checkout_request_id,
        'ResultCode': result_code,
        'ResultDesc': 'The service request is processed.',
    }
    if metadata is not None:
        callback['CallbackMetadata'] = {
            'Item': [{'Name': key, 'Value': value} for key, value in metadata.items()],
        }
    return {'Body': {'stkCallback': callback}}


def confirm_stay_booking(booking_id):
    """Mark a stay booking as paid so customer and vendor changes are allowed."""
    with application.app.app_context():
        booking = application.db.session.get(application.Booking, booking_id)
        booking.payment_status = 'paid'
        booking.status = 'confirmed'
        application.db.session.commit()


def book_stay(stay, room, check_in, check_out, guests=2):
    response = stay['guest']['client'].post(
        '/booking-confirmation',
        json=stay_booking_payload(stay, room, check_in, check_out, guests=guests),
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()['booking']


# Room inventory


def test_vendor_manages_room_inventory_on_own_properties_only(vendor_pair):
    owner, owner_headers, _ = vendor_pair[0]
    other, other_headers, _ = vendor_pair[1]
    listing = create_property(owner, owner_headers)
    room = create_room(owner, owner_headers, listing['id'], {
        'name': 'Garden suite',
        'guests': 3,
        'base_rate': 9000,
        'total_units': 2,
    })

    rooms = owner.get(f"/api/vendor/properties/{listing['id']}/rooms")
    assert rooms.status_code == 200
    assert [item['name'] for item in rooms.get_json()['rooms']] == ['Garden suite']
    assert rooms.get_json()['property']['slug'] == listing['slug']

    updated = owner.put(
        f"/api/vendor/properties/{listing['id']}/rooms/{room['id']}",
        json={'name': 'Garden suite deluxe', 'guests': 4, 'base_rate': 9500, 'total_units': 3},
        headers=owner_headers,
    )
    assert updated.status_code == 200
    saved = updated.get_json()['room']
    assert saved['name'] == 'Garden suite deluxe'
    assert saved['guests'] == 4
    assert saved['base_rate'] == 9500
    assert saved['total_units'] == 3

    assert other.get(f"/api/vendor/properties/{listing['id']}/rooms").status_code == 404
    assert other.post(
        f"/api/vendor/properties/{listing['id']}/rooms",
        json={'name': 'Intruder room', 'guests': 2, 'base_rate': 5000, 'total_units': 1},
        headers=other_headers,
    ).status_code == 404
    assert other.put(
        f"/api/vendor/properties/{listing['id']}/rooms/{room['id']}",
        json={'name': 'Intruder rename'},
        headers=other_headers,
    ).status_code == 404
    assert other.delete(
        f"/api/vendor/properties/{listing['id']}/rooms/{room['id']}", headers=other_headers
    ).status_code == 404
    assert other.get(f"/api/vendor/properties/{listing['id']}/rooms/{room['id']}").status_code == 404

    assert owner.delete(
        f"/api/vendor/properties/{listing['id']}/rooms/{room['id']}", headers=owner_headers
    ).status_code == 204
    assert owner.get(f"/api/vendor/properties/{listing['id']}/rooms").get_json()['rooms'] == []


def test_admin_manages_rooms_on_any_listing(admin_client, vendor_pair):
    admin, admin_headers = admin_client
    owner, owner_headers, _ = vendor_pair[0]
    listing = create_property(owner, owner_headers)

    response = admin.post(
        f"/api/admin/properties/{listing['id']}/rooms",
        json={'name': 'Admin managed room', 'guests': 2, 'base_rate': 6000, 'total_units': 2},
        headers=admin_headers,
    )
    assert response.status_code == 201
    room_id = response.get_json()['room']['id']
    assert admin.get(f"/api/admin/properties/{listing['id']}/rooms").get_json()['rooms'][0]['id'] == room_id
    assert admin.delete(
        f"/api/admin/properties/{listing['id']}/rooms/{room_id}", headers=admin_headers
    ).status_code == 204


def test_room_creation_validates_values_and_csrf(vendor_pair):
    owner, owner_headers, _ = vendor_pair[0]
    listing = create_property(owner, owner_headers)
    endpoint = f"/api/vendor/properties/{listing['id']}/rooms"

    for payload in (
        {'name': '', 'guests': 2, 'base_rate': 5000, 'total_units': 1},
        {'name': 'Bad rate', 'guests': 2, 'base_rate': 0, 'total_units': 1},
        {'name': 'Bad guests', 'guests': 0, 'base_rate': 5000, 'total_units': 1},
        {'name': 'Bad units', 'guests': 2, 'base_rate': 5000, 'total_units': 0},
        {'name': 'Bad units cap', 'guests': 2, 'base_rate': 5000, 'total_units': 501},
        {'name': 'x' * 121, 'guests': 2, 'base_rate': 5000, 'total_units': 1},
    ):
        assert owner.post(endpoint, json=payload, headers=owner_headers).status_code == 400

    assert owner.post(endpoint, json={
        'name': 'Missing csrf', 'guests': 2, 'base_rate': 5000, 'total_units': 1,
    }).status_code == 403
    assert owner.get(endpoint).get_json()['rooms'] == []


# Availability calendar


def test_vendor_sets_rates_units_and_closures_across_a_range(vendor_pair):
    owner, owner_headers, _ = vendor_pair[0]
    listing = create_property(owner, owner_headers)
    room = create_room(owner, owner_headers, listing['id'], {'base_rate': 7000, 'total_units': 2})
    start = datetime.now(KENYA_TIMEZONE).date() + timedelta(days=12)
    check_in, check_out = start.isoformat(), (start + timedelta(days=3)).isoformat()
    last_night = (start + timedelta(days=2)).isoformat()
    endpoint = f"/api/vendor/properties/{listing['id']}/rooms/{room['id']}/availability"

    response = owner.put(endpoint, json={
        'from': check_in, 'to': last_night, 'rate': 11000, 'units_available': 1,
    }, headers=owner_headers)
    assert response.status_code == 200
    calendar = response.get_json()['calendar']
    assert [day['date'] for day in calendar] == night_keys(check_in, check_out)
    assert {day['rate'] for day in calendar} == {11000}
    assert {day['units'] for day in calendar} == {1}
    assert {day['remaining'] for day in calendar} == {1}
    assert all(day['has_override'] for day in calendar)

    closed = owner.put(endpoint, json={
        'from': check_in, 'to': check_in, 'is_closed': True,
    }, headers=owner_headers)
    assert closed.status_code == 200
    first_night = closed.get_json()['calendar'][0]
    assert first_night['is_closed'] is True
    assert first_night['remaining'] == 0
    assert first_night['rate'] == 11000

    fetched = owner.get(f'{endpoint}?from={check_in}&to={check_out}')
    assert fetched.status_code == 200
    days = fetched.get_json()['calendar']
    assert len(days) == 4
    assert days[0]['is_closed'] is True
    assert days[1]['is_closed'] is False

    cleared = owner.delete(f'{endpoint}?date={check_in}', headers=owner_headers)
    assert cleared.status_code == 204
    day = owner.get(f'{endpoint}?from={check_in}&to={check_in}').get_json()['calendar'][0]
    assert day['has_override'] is False
    assert day['is_closed'] is False
    assert day['rate'] == 7000
    assert day['units'] == 2


def test_availability_updates_reject_bad_ranges_and_missing_csrf(vendor_pair):
    owner, owner_headers, _ = vendor_pair[0]
    listing = create_property(owner, owner_headers)
    room = create_room(owner, owner_headers, listing['id'])
    start = datetime.now(KENYA_TIMEZONE).date() + timedelta(days=10)
    check_in = start.isoformat()
    endpoint = f"/api/vendor/properties/{listing['id']}/rooms/{room['id']}/availability"

    backwards = owner.put(endpoint, json={
        'from': check_in, 'to': (start - timedelta(days=2)).isoformat(), 'rate': 5000,
    }, headers=owner_headers)
    assert backwards.status_code == 400
    assert 'end date' in backwards.get_json()['error']

    too_long = owner.put(endpoint, json={
        'from': check_in, 'to': (start + timedelta(days=200)).isoformat(), 'rate': 5000,
    }, headers=owner_headers)
    assert too_long.status_code == 400

    assert owner.put(endpoint, json={'from': check_in, 'to': check_in}, headers=owner_headers).status_code == 400
    assert owner.put(endpoint, json={
        'from': check_in, 'to': check_in, 'rate': 0,
    }, headers=owner_headers).status_code == 400
    assert owner.put(endpoint, json={
        'from': check_in, 'to': check_in, 'units_available': 600,
    }, headers=owner_headers).status_code == 400
    assert owner.put(endpoint, json={'from': check_in, 'to': check_in, 'rate': 5000}).status_code == 403
    assert owner.put(endpoint, json={
        'from': 'not-a-date', 'to': 'not-a-date', 'rate': 5000,
    }, headers=owner_headers).status_code == 400

    other_headers = vendor_pair[1][1]
    assert vendor_pair[1][0].put(endpoint, json={
        'from': check_in, 'to': check_in, 'rate': 5000,
    }, headers=other_headers).status_code == 404


def test_public_quote_applies_nightly_overrides_and_capacity(stay):
    owner, owner_headers = stay['owner'], stay['owner_headers']
    room = stay['rooms']['double']
    start = datetime.now(KENYA_TIMEZONE).date() + timedelta(days=15)
    check_in, check_out = start.isoformat(), (start + timedelta(days=2)).isoformat()
    endpoint = f"/api/vendor/properties/{stay['property']['id']}/rooms/{room['id']}/availability"

    assert owner.put(endpoint, json={
        'from': check_in, 'to': check_in, 'rate': 10000,
    }, headers=owner_headers).status_code == 200

    visitor = application.app.test_client()
    response = visitor.get(
        f"/api/properties/{stay['slug']}/availability"
        f'?check_in={check_in}&check_out={check_out}&guests=2'
    )
    assert response.status_code == 200
    quote = response.get_json()
    assert quote['nights'] == 2
    assert quote['check_in'] == check_in
    assert quote['check_out'] == check_out
    assert quote['property']['slug'] == stay['slug']

    option = next(item for item in quote['rooms'] if item['id'] == room['id'])
    assert [night['rate'] for night in option['nightly']] == [10000, 8000]
    assert option['total'] == 18000
    assert option['remaining'] == 2
    assert option['is_available'] is True

    too_many = visitor.get(
        f"/api/properties/{stay['slug']}/availability"
        f'?check_in={check_in}&check_out={check_out}&guests=6'
    ).get_json()
    assert next(item for item in too_many['rooms'] if item['id'] == room['id'])['is_available'] is False


def test_public_quote_rejects_invalid_dates_and_unknown_listings(stay):
    visitor = application.app.test_client()
    check_in, check_out = stay_dates(18, 2)

    assert visitor.get(
        f"/api/properties/{stay['slug']}/availability"
        f'?check_in={check_in}&check_out={check_in}'
    ).status_code == 400
    assert visitor.get(
        f"/api/properties/{stay['slug']}/availability"
        '?check_in=2020-01-01&check_out=2020-01-03'
    ).status_code == 400
    assert visitor.get(
        f"/api/properties/{stay['slug']}/availability"
        f'?check_in={check_in}&check_out={check_out}&guests=many'
    ).status_code == 400
    assert visitor.get(
        '/api/properties/no-such-accommodation/availability'
        f'?check_in={check_in}&check_out={check_out}'
    ).status_code == 404


# Instant stay booking


def test_stay_booking_reserves_nights_and_prices_on_the_server(stay):
    guest = stay['guest']
    room = stay['rooms']['double']
    check_in, check_out = stay_dates()
    payload = stay_booking_payload(stay, room, check_in, check_out, guests=2)
    payload['amount'] = 1
    payload['total_amount'] = 1

    response = guest['client'].post('/booking-confirmation', json=payload)
    assert response.status_code == 201
    booking = response.get_json()['booking']

    # 16,000 subtotal + 1,440 service fee + 100 booking fee = 17,540 charged.
    assert booking['subtotal_amount'] == 16000
    assert booking['service_fee_amount'] == 1440
    assert booking['booking_fee_amount'] == 100
    assert booking['guest_service_fee_rate'] == 9
    assert booking['amount'] == 17540
    assert booking['host_commission_rate'] == 4
    assert booking['host_commission_amount'] == 640
    assert booking['host_payout_amount'] == 15360
    assert booking['booking_type'] == 'property'
    assert booking['property_id'] == stay['property']['id']
    assert booking['room_id'] == room['id']
    assert booking['check_in'] == check_in
    assert booking['check_out'] == check_out
    assert booking['nights'] == 2
    assert booking['schedule_id'] is None
    assert booking['time'] == ''
    assert booking['tour'] == stay['slug']
    assert booking['guests'] == 2
    assert booking['status'] == 'requested'
    assert booking['payment_status'] == 'pending'
    assert booking['user_id'] == guest['user_id']

    with application.app.app_context():
        assert reserved_nights(room['id'], check_in, check_out) == {key: 1 for key in night_keys(check_in, check_out)}
        saved = application.db.session.get(application.Booking, booking['id'])
        assert saved.commission_rate == float(application.get_admin_setting('host_commission_rate', 4))
        assert saved.subtotal_amount == 16000
        assert saved.host_payout_amount == 15360

    customer_view = guest['client'].get('/api/customer/bookings').get_json()['bookings']
    row = next(item for item in customer_view if item['id'] == booking['id'])
    assert row['property_name'] == stay['property']['name']
    assert row['room_name'] == 'Garden double'
    assert row['check_in'] == check_in
    assert row['check_out'] == check_out


def test_second_booking_on_a_single_unit_room_is_refused(stay):
    guest = stay['guest']
    room = stay['rooms']['single']
    check_in, check_out = stay_dates(20, 2)

    first = guest['client'].post(
        '/booking-confirmation', json=stay_booking_payload(stay, room, check_in, check_out, guests=2)
    )
    assert first.status_code == 201
    second = guest['client'].post(
        '/booking-confirmation', json=stay_booking_payload(stay, room, check_in, check_out, guests=2)
    )
    assert second.status_code == 409
    assert 'no longer available' in second.get_json()['error']
    with application.app.app_context():
        assert reserved_nights(room['id'], check_in, check_out) == {key: 1 for key in night_keys(check_in, check_out)}


def test_availability_unit_cap_limits_stay_bookings(stay):
    owner, owner_headers = stay['owner'], stay['owner_headers']
    room = stay['rooms']['double']
    check_in, check_out = stay_dates(25, 2)
    endpoint = f"/api/vendor/properties/{stay['property']['id']}/rooms/{room['id']}/availability"

    assert owner.put(endpoint, json={
        'from': check_in, 'to': night_keys(check_in, check_out)[-1], 'units_available': 1,
    }, headers=owner_headers).status_code == 200

    visitor = application.app.test_client()
    quote = visitor.get(
        f"/api/properties/{stay['slug']}/availability"
        f'?check_in={check_in}&check_out={check_out}&guests=2'
    ).get_json()
    assert next(item for item in quote['rooms'] if item['id'] == room['id'])['remaining'] == 1

    first = stay['guest']['client'].post(
        '/booking-confirmation', json=stay_booking_payload(stay, room, check_in, check_out, guests=2)
    )
    assert first.status_code == 201
    sold_out = visitor.get(
        f"/api/properties/{stay['slug']}/availability"
        f'?check_in={check_in}&check_out={check_out}&guests=2'
    ).get_json()
    assert next(item for item in sold_out['rooms'] if item['id'] == room['id'])['is_available'] is False
    assert stay['guest']['client'].post(
        '/booking-confirmation', json=stay_booking_payload(stay, room, check_in, check_out, guests=2)
    ).status_code == 409


def test_stay_booking_validates_room_dates_and_capacity(stay):
    guest = stay['guest']
    room = stay['rooms']['double']
    check_in, check_out = stay_dates(28, 2)
    endpoint = '/booking-confirmation'

    too_many = guest['client'].post(
        endpoint, json=stay_booking_payload(stay, room, check_in, check_out, guests=room['guests'] + 1)
    )
    assert too_many.status_code == 400
    assert str(room['guests']) in too_many.get_json()['error']

    unknown_property = guest['client'].post(
        endpoint,
        json=stay_booking_payload(stay, room, check_in, check_out, tour='no-such-accommodation'),
    )
    assert unknown_property.status_code == 400

    stranger = create_property(stay['owner'], stay['owner_headers'])
    stranger_room = create_room(stay['owner'], stay['owner_headers'], stranger['id'])
    wrong_room = guest['client'].post(
        endpoint, json=stay_booking_payload(stay, stranger_room, check_in, check_out)
    )
    assert wrong_room.status_code == 400

    same_day = guest['client'].post(
        endpoint, json=stay_booking_payload(stay, room, check_in, check_in)
    )
    assert same_day.status_code == 400

    past = guest['client'].post(
        endpoint, json=stay_booking_payload(stay, room, '2020-01-01', '2020-01-03')
    )
    assert past.status_code == 400

    too_long = guest['client'].post(
        endpoint, json=stay_booking_payload(stay, room, check_in, stay_dates(60, 3)[1])
    )
    assert too_long.status_code == 400

    with application.app.app_context():
        saved_room = application.db.session.get(application.PropertyRoom, room['id'])
        saved_room.is_active = False
        application.db.session.commit()
    inactive = guest['client'].post(
        endpoint, json=stay_booking_payload(stay, room, check_in, check_out)
    )
    assert inactive.status_code == 400

    with application.app.app_context():
        assert reserved_nights(room['id'], check_in, check_out) == {key: 0 for key in night_keys(check_in, check_out)}
        assert application.Booking.query.filter_by(user_id=guest['user_id']).count() == 0


# M-Pesa lifecycle


def test_successful_callback_confirms_stay_and_keeps_nights(stay, monkeypatch):
    room = stay['rooms']['double']
    check_in, check_out = stay_dates(40, 2)
    booking_data = book_stay(stay, room, check_in, check_out)

    with application.app.app_context():
        booking = application.db.session.get(application.Booking, booking_data['id'])
        callback = _daraja_callback(booking, 0, {
            'Amount': int(round(booking.amount)),
            'MpesaReceiptNumber': 'STAY123ABC',
            'PhoneNumber': 254712345678,
        })
    monkeypatch.setattr(application, 'query_stk_push', lambda checkout_id: {
        'ResponseCode': '0',
        'ResultCode': '0',
        'CheckoutRequestID': checkout_id,
    })

    result = stay['guest']['client'].post('/daraja/callback', json=callback)

    assert result.status_code == 204
    with application.app.app_context():
        booking = application.db.session.get(application.Booking, booking_data['id'])
        assert booking.payment_status == 'paid'
        assert booking.status == 'confirmed'
        assert booking.mpesa_receipt_number == 'STAY123ABC'
        assert reserved_nights(room['id'], check_in, check_out) == {key: 1 for key in night_keys(check_in, check_out)}


def test_failed_callback_releases_stay_nights(stay, monkeypatch):
    room = stay['rooms']['double']
    check_in, check_out = stay_dates(45, 2)
    booking_data = book_stay(stay, room, check_in, check_out)

    with application.app.app_context():
        booking = application.db.session.get(application.Booking, booking_data['id'])
        callback = _daraja_callback(booking, 1032)
    monkeypatch.setattr(application, 'query_stk_push', lambda checkout_id: {
        'ResponseCode': '0',
        'ResultCode': '1032',
        'CheckoutRequestID': checkout_id,
        'ResultDesc': 'Request cancelled by the user.',
    })

    result = stay['guest']['client'].post('/daraja/callback', json=callback)

    assert result.status_code == 204
    with application.app.app_context():
        booking = application.db.session.get(application.Booking, booking_data['id'])
        assert booking.payment_status == 'failed'
        assert booking.status == 'cancelled'
        assert reserved_nights(room['id'], check_in, check_out) == {key: 0 for key in night_keys(check_in, check_out)}


def test_rejected_stk_push_releases_stay_nights(stay, monkeypatch):
    room = stay['rooms']['double']
    check_in, check_out = stay_dates(48, 2)

    def reject_payment(phone, amount, booking_id):
        raise application.DarajaError('The payment request was rejected.')

    monkeypatch.setattr(application, 'initiate_stk_push', reject_payment)

    response = stay['guest']['client'].post(
        '/booking-confirmation', json=stay_booking_payload(stay, room, check_in, check_out)
    )

    assert response.status_code == 503
    with application.app.app_context():
        booking = application.Booking.query.filter_by(
            user_id=stay['guest']['user_id']
        ).order_by(application.Booking.id.desc()).first()
        assert booking.payment_status == 'failed'
        assert booking.status == 'cancelled'
        assert reserved_nights(room['id'], check_in, check_out) == {key: 0 for key in night_keys(check_in, check_out)}


# Customer cancellations


def test_customer_cancel_releases_stay_nights(stay):
    guest = stay['guest']
    room = stay['rooms']['double']
    check_in, check_out = stay_dates(20, 3)
    booking_data = book_stay(stay, room, check_in, check_out)
    confirm_stay_booking(booking_data['id'])

    response = guest['client'].post(
        f"/api/customer/bookings/{booking_data['id']}/cancel",
        headers={'X-CSRF-Token': guest['csrf']},
    )

    assert response.status_code == 200
    assert response.get_json()['booking']['status'] == 'cancelled'
    with application.app.app_context():
        assert reserved_nights(room['id'], check_in, check_out) == {key: 0 for key in night_keys(check_in, check_out)}


def test_stay_changes_are_blocked_inside_the_cutoff_and_never_rescheduled(stay):
    guest = stay['guest']
    room = stay['rooms']['double']
    check_in, check_out = stay_dates(1, 2)
    booking_data = book_stay(stay, room, check_in, check_out)
    confirm_stay_booking(booking_data['id'])

    reschedule = guest['client'].post(
        f"/api/customer/bookings/{booking_data['id']}/reschedule",
        json={'schedule_id': 1},
        headers={'X-CSRF-Token': guest['csrf']},
    )
    assert reschedule.status_code == 409
    assert 'cannot be rescheduled' in reschedule.get_json()['error']

    blocked = guest['client'].post(
        f"/api/customer/bookings/{booking_data['id']}/cancel",
        headers={'X-CSRF-Token': guest['csrf']},
    )
    assert blocked.status_code == 400
    assert 'before check-in' in blocked.get_json()['error']
    with application.app.app_context():
        assert reserved_nights(room['id'], check_in, check_out) == {key: 1 for key in night_keys(check_in, check_out)}


# Vendor stay bookings


def test_vendor_bookings_include_stays_and_allow_completion(stay):
    owner, owner_headers = stay['owner'], stay['owner_headers']
    room = stay['rooms']['double']
    check_in, check_out = stay_dates(50, 2)
    booking_data = book_stay(stay, room, check_in, check_out)
    confirm_stay_booking(booking_data['id'])

    rows = owner.get('/api/vendor/bookings').get_json()['bookings']
    row = next(item for item in rows if item['id'] == booking_data['id'])
    assert row['booking_type'] == 'property'
    assert row['property_name'] == stay['property']['name']
    assert row['tour_name'] == stay['property']['name']
    assert row['room_name'] == 'Garden double'
    assert row['check_in'] == check_in
    assert row['check_out'] == check_out
    assert row['nights'] == 2

    assert stay['other']['client'].get('/api/vendor/bookings').get_json()['bookings'] == []
    assert stay['other']['client'].post(
        f"/api/vendor/bookings/{booking_data['id']}/status",
        json={'status': 'completed'},
        headers=stay['other']['headers'],
    ).status_code == 404

    assert owner.post(
        f"/api/vendor/bookings/{booking_data['id']}/status",
        json={'status': 'confirmed'},
        headers=owner_headers,
    ).status_code == 409

    completed = owner.post(
        f"/api/vendor/bookings/{booking_data['id']}/status",
        json={'status': 'completed'},
        headers=owner_headers,
    )
    assert completed.status_code == 200
    assert completed.get_json()['booking']['status'] == 'completed'


def test_vendor_cancelling_a_stay_releases_nights(stay):
    owner, owner_headers = stay['owner'], stay['owner_headers']
    room = stay['rooms']['double']
    check_in, check_out = stay_dates(55, 2)
    booking_data = book_stay(stay, room, check_in, check_out)
    confirm_stay_booking(booking_data['id'])

    response = owner.post(
        f"/api/vendor/bookings/{booking_data['id']}/status",
        json={'status': 'cancelled'},
        headers=owner_headers,
    )

    assert response.status_code == 200
    assert response.get_json()['booking']['status'] == 'cancelled'
    with application.app.app_context():
        assert reserved_nights(room['id'], check_in, check_out) == {key: 0 for key in night_keys(check_in, check_out)}


# Migrations


def test_properties_without_rooms_get_a_bookable_default_room():
    token = _token()
    with application.app.app_context():
        listing = application.Property(
            slug=f'default-room-{token}',
            owner_name='Backfill owner',
            owner_email=f'{token}@example.test',
            name=f'Backfill listing {token}',
            property_type='apartment',
            location='Lamu',
            price_per_night=6500,
            guests=2,
            description='A listing saved before rooms existed.',
        )
        application.db.session.add(listing)
        application.db.session.commit()
        property_id = listing.id
        assert application.PropertyRoom.query.filter_by(property_id=property_id).count() == 0

        application.ensure_catalog_columns()

        rooms = application.PropertyRoom.query.filter_by(property_id=property_id).all()
        assert len(rooms) == 1
        assert rooms[0].name == 'Entire place'
        assert rooms[0].guests == 2
        assert rooms[0].base_rate == 6500
        assert rooms[0].total_units == 1

        application.ensure_catalog_columns()
        assert application.PropertyRoom.query.filter_by(property_id=property_id).count() == 1

        _cleanup_property(application.db.session.get(application.Property, property_id))
        application.db.session.commit()
