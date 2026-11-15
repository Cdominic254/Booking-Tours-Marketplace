import hashlib
import io
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

import app as application


@pytest.fixture
def admin_client():
    email = f"catalogue-test-{uuid.uuid4().hex}@example.test"
    with application.app.app_context():
        admin = application.AdminAccount(
            name='Catalogue test',
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
    vendors = []
    with application.app.app_context():
        for label in ('one', 'two'):
            email = f'vendor-{label}-{uuid.uuid4().hex}@example.test'
            vendor = application.VendorAccount(
                name=f'Test Vendor {label}',
                email=email,
                password_hash=application.generate_password_hash('test-vendor-password'),
            )
            application.db.session.add(vendor)
            vendors.append((email, vendor))
        application.db.session.commit()
        vendor_accounts = [(email, vendor.id) for email, vendor in vendors]
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
                    booking_id for (booking_id,) in application.db.session.query(application.Booking.id).filter_by(tour=tour.slug).all()
                ]
                if booking_ids:
                    application.BookingDispute.query.filter(application.BookingDispute.booking_id.in_(booking_ids)).delete(synchronize_session=False)
                application.Booking.query.filter_by(tour=tour.slug).delete()
                application.TourSchedule.query.filter_by(tour_slug=tour.slug).delete()
                application.Review.query.filter_by(target_type='tour', target_id=tour.slug).delete()
                application.db.session.delete(tour)
            for listing in application.Property.query.filter_by(vendor_id=vendor_id).all():
                application.Review.query.filter_by(target_type='property', target_id=listing.slug).delete()
                application.db.session.delete(listing)
            vendor = application.db.session.get(application.VendorAccount, vendor_id)
            if vendor:
                application.db.session.delete(vendor)
        application.db.session.commit()


def test_admin_operations_manage_accounts_bookings_refunds_disputes_and_analytics(admin_client, vendor_pair):
    admin, headers = admin_client
    vendor_client, vendor_headers, vendor_id = vendor_pair[0]
    customer_email = f'customer-{uuid.uuid4().hex}@example.test'
    with application.app.app_context():
        vendor_email = application.db.session.get(application.VendorAccount, vendor_id).email
        original_host_rate = float(application.get_admin_setting('host_commission_rate', 4))
        original_subscriber_rate = float(application.get_admin_setting('subscriber_host_commission_rate', 2.5))
        original_guest_rate = float(application.get_admin_setting('guest_service_fee_rate', 9))
        original_booking_fee = float(application.get_admin_setting('booking_fee', 100))
        original_subscription_fee = float(application.get_admin_setting('subscription_monthly_fee', 2500))
    if (original_host_rate, original_subscriber_rate, original_guest_rate, original_booking_fee, original_subscription_fee) != (4.0, 2.5, 9.0, 100.0, 2500.0):
        assert admin.put('/api/admin/settings', json={
            'host_commission_rate': 4,
            'subscriber_host_commission_rate': 2.5,
            'guest_service_fee_rate': 9,
            'booking_fee': 100,
            'subscription_monthly_fee': 2500,
        }, headers=headers).status_code == 200
    with application.app.app_context():
        customer = application.User(
            name='Operations Customer',
            email=customer_email,
            password_hash=application.generate_password_hash('customer-password'),
        )
        tour = application.Tour(
            slug=f'operations-tour-{vendor_id}',
            vendor_id=vendor_id,
            name='Operations Sailing',
            description='A tour used to test admin operations.',
            duration='Two hours',
            price=2500,
        )
        application.db.session.add_all([customer, tour])
        application.db.session.flush()
        departure = application.TourSchedule(
            tour_slug=tour.slug,
            starts_at=(datetime.now(ZoneInfo('Africa/Nairobi')).replace(tzinfo=None) + timedelta(days=8)).replace(second=0, microsecond=0),
            capacity=6,
            booked_count=2,
        )
        application.db.session.add(departure)
        application.db.session.flush()
        fee_quote = application.split_fee_quote(5000)
        booking = application.Booking(
            user_id=customer.id,
            schedule_id=departure.id,
            name=customer.name,
            email=customer.email,
            phone='+254712345678',
            tour=tour.slug,
            date=departure.starts_at.date().isoformat(),
            time=departure.starts_at.strftime('%H:%M'),
            guests=2,
            amount=fee_quote['total'],
            subtotal_amount=fee_quote['subtotal'],
            service_fee_amount=fee_quote['guest_service_fee'],
            booking_fee_amount=fee_quote['booking_fee'],
            host_commission_amount=fee_quote['host_commission'],
            host_payout_amount=fee_quote['host_payout'],
            host_commission_rate=fee_quote['host_commission_rate'],
            guest_service_fee_rate=fee_quote['guest_service_fee_rate'],
            commission_rate=fee_quote['host_commission_rate'],
            payment_status='paid',
            status='confirmed',
        )
        application.db.session.add(booking)
        application.db.session.commit()
        booking_id = booking.id
        customer_id = customer.id
        departure_id = departure.id
        tour_slug = tour.slug

    response = admin.get('/api/admin/operations')
    assert response.status_code == 200
    operations = response.get_json()
    assert operations['settings'] == {
        'host_commission_rate': 4.0,
        'subscriber_host_commission_rate': 2.5,
        'guest_service_fee_rate': 9.0,
        'booking_fee': 100.0,
        'subscription_monthly_fee': 2500.0,
        'refund_policy': 'automatic',
        'cancellation_window_hours': 48,
    }
    assert operations['refunds_due'] == {'count': 0, 'amount': 0}
    assert operations['analytics']['paid_revenue'] == 5550
    assert operations['analytics']['commission_earned'] == 750
    assert operations['analytics']['host_payout_due'] == 4800
    assert operations['analytics']['by_tour'][0]['tour_name'] == 'Operations Sailing'
    assert operations['analytics']['by_tour'][0]['host_payout'] == 4800
    assert next(row for row in operations['customers'] if row['id'] == customer_id)['booking_count'] == 1

    assert admin.put('/api/admin/settings', json={
        'host_commission_rate': 26,
        'subscriber_host_commission_rate': 2.5,
        'guest_service_fee_rate': 9,
        'booking_fee': 100,
        'subscription_monthly_fee': 2500,
    }, headers=headers).status_code == 400
    assert admin.put('/api/admin/settings', json={
        'host_commission_rate': 4,
        'subscriber_host_commission_rate': 2.5,
        'guest_service_fee_rate': 9,
        'booking_fee': -50,
        'subscription_monthly_fee': 2500,
    }, headers=headers).status_code == 400
    assert admin.put('/api/admin/settings', json={
        'host_commission_rate': 4,
        'subscriber_host_commission_rate': 2.5,
        'guest_service_fee_rate': 9,
        'booking_fee': 100,
        'subscription_monthly_fee': -1,
    }, headers=headers).status_code == 400
    response = admin.put('/api/admin/settings', json={
        'host_commission_rate': 5,
        'subscriber_host_commission_rate': 3,
        'guest_service_fee_rate': 10,
        'booking_fee': 150,
        'subscription_monthly_fee': 3000,
    }, headers=headers)
    assert response.status_code == 200
    assert response.get_json()['settings']['host_commission_rate'] == 5
    assert response.get_json()['settings']['subscriber_host_commission_rate'] == 3
    assert response.get_json()['settings']['guest_service_fee_rate'] == 10
    assert response.get_json()['settings']['booking_fee'] == 150
    assert response.get_json()['settings']['subscription_monthly_fee'] == 3000
    assert admin.put(
        '/api/admin/settings',
        json={'host_commission_rate': 5, 'subscriber_host_commission_rate': 3, 'guest_service_fee_rate': 10, 'booking_fee': 150, 'subscription_monthly_fee': 3000, 'refund_policy': 'automatic'},
        headers=headers,
    ).status_code == 200
    assert admin.put(
        '/api/admin/settings',
        json={'host_commission_rate': 5, 'subscriber_host_commission_rate': 3, 'guest_service_fee_rate': 10, 'booking_fee': 150, 'subscription_monthly_fee': 3000, 'refund_policy': 'manual_review'},
        headers=headers,
    ).status_code == 400

    assert admin.post(
        f'/api/admin/users/customer/{customer_id}/status',
        json={'active': False},
        headers=headers,
    ).status_code == 200
    inactive_customer_login = application.app.test_client().post('/login', data={
        'email': customer_email,
        'password': 'customer-password',
    })
    assert inactive_customer_login.status_code == 302
    assert 'Invalid%20email' in inactive_customer_login.location
    assert admin.post(
        f'/api/admin/users/vendor/{vendor_id}/status',
        json={'active': False},
        headers=headers,
    ).status_code == 200
    assert vendor_client.get('/api/vendor/catalogue').status_code == 401
    inactive_login = application.app.test_client().post('/vendor/login', data={
        'email': vendor_email,
        'password': 'test-vendor-password',
    })
    assert inactive_login.status_code == 302
    assert 'Invalid%20partner%20email' in inactive_login.location
    assert admin.post(
        f'/api/admin/users/customer/{customer_id}/status',
        json={'active': True},
        headers=headers,
    ).status_code == 200
    assert admin.post(
        f'/api/admin/users/vendor/{vendor_id}/status',
        json={'active': True},
        headers=headers,
    ).status_code == 200

    response = admin.post(
        f'/api/admin/bookings/{booking_id}/refund',
        json={'status': 'pending', 'reason': 'Customer asked for the money back.'},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.get_json()['booking']['refund_status'] == 'pending'
    assert response.get_json()['booking']['refund_amount'] == 5550
    assert admin.get('/api/admin/operations').get_json()['refunds_due'] == {'count': 1, 'amount': 5550}
    assert admin.post(
        f'/api/admin/bookings/{booking_id}/refund',
        json={'status': 'approved'},
        headers=headers,
    ).status_code == 409
    response = admin.post(
        f'/api/admin/bookings/{booking_id}/refund',
        json={'status': 'paid'},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.get_json()['gateway_refund_issued'] is False
    assert response.get_json()['booking']['refund_status'] == 'paid'
    assert response.get_json()['booking']['refund_paid_at']
    assert response.get_json()['booking']['payment_status'] == 'refunded'
    assert admin.get('/api/admin/operations').get_json()['refunds_due'] == {'count': 0, 'amount': 0}
    refunded_tour = next(
        row for row in admin.get('/api/admin/operations').get_json()['analytics']['by_tour']
        if row['tour'] == tour_slug
    )
    assert refunded_tour['paid_revenue'] == 0

    response = admin.post(
        f'/api/admin/bookings/{booking_id}/disputes',
        json={'reason': 'Customer reports a disagreement about the tour service.'},
        headers=headers,
    )
    assert response.status_code == 201
    dispute_id = response.get_json()['dispute']['id']
    assert admin.put(
        f'/api/admin/disputes/{dispute_id}',
        json={'resolution': 'Reviewed with the operator and documented the agreed outcome.'},
        headers=headers,
    ).status_code == 200
    assert admin.put(
        f'/api/admin/disputes/{dispute_id}',
        json={'resolution': 'Trying to resolve the same case a second time.'},
        headers=headers,
    ).status_code == 409

    assert admin.post(f'/api/admin/bookings/{booking_id}/cancel', headers=headers).status_code == 200
    with application.app.app_context():
        assert application.db.session.get(application.TourSchedule, departure_id).booked_count == 0
        assert application.db.session.get(application.Booking, booking_id).commission_rate == 4
        application.BookingDispute.query.filter_by(booking_id=booking_id).delete()
        application.db.session.delete(application.db.session.get(application.Booking, booking_id))
        application.db.session.delete(application.db.session.get(application.TourSchedule, departure_id))
        application.db.session.delete(application.db.session.get(application.User, customer_id))
        application.db.session.commit()
    assert admin.put(
        '/api/admin/settings',
        json={'host_commission_rate': original_host_rate, 'subscriber_host_commission_rate': original_subscriber_rate, 'guest_service_fee_rate': original_guest_rate, 'booking_fee': original_booking_fee, 'subscription_monthly_fee': original_subscription_fee},
        headers=headers,
    ).status_code == 200


def test_admin_analytics_tracks_funnel_sources_occupancy_and_property_revenue(admin_client):
    admin, _ = admin_client
    visitor = application.app.test_client()
    first_event = visitor.post('/api/analytics/events', json={
        'page': '/',
        'source': 'https://www.instagram.com/safarinasstay/',
    })
    assert first_event.status_code == 204
    assert application.normalize_analytics_source('instagram') == 'Instagram'
    with visitor.session_transaction() as browser_session:
        visitor_token = browser_session['analytics_visitor_token']
        assert browser_session['analytics_source'] == 'Instagram'
    visitor_key = hashlib.sha256(visitor_token.encode('utf-8')).hexdigest()
    assert visitor.post('/api/analytics/events', json={
        'page': '/booking.html',
        'source': 'https://www.google.com/',
    }).status_code == 204

    slug_suffix = uuid.uuid4().hex
    tour_slug = f'analytics-tour-{slug_suffix}'
    property_slug = f'analytics-stay-{slug_suffix}'
    with application.app.app_context():
        tour = application.Tour(
            slug=tour_slug,
            name='Analytics tour',
            description='Analytics occupancy fixture.',
            duration='One hour',
            price=1000,
        )
        property_listing = application.Property(
            slug=property_slug,
            owner_name='Analytics owner',
            owner_email=f'{slug_suffix}@example.test',
            name='Analytics rental',
            property_type='rental',
            location='Lamu',
            price_per_night=12000,
            guests=4,
            description='Analytics property revenue fixture.',
        )
        application.db.session.add_all([tour, property_listing])
        application.db.session.flush()
        departure = application.TourSchedule(
            tour_slug=tour_slug,
            starts_at=(datetime.now(ZoneInfo('Africa/Nairobi')).replace(tzinfo=None) + timedelta(days=4)).replace(second=0, microsecond=0),
            capacity=6,
            booked_count=3,
        )
        booking = application.Booking(
            name='Analytics guest',
            email=f'guest-{slug_suffix}@example.test',
            phone='+254712345678',
            tour=property_slug,
            date=datetime.now().date().isoformat(),
            time='12:00',
            guests=1,
            amount=12000,
            payment_status='paid',
            traffic_source='Instagram',
            status='confirmed',
        )
        application.db.session.add_all([departure, booking])
        application.db.session.commit()
        target_month = departure.starts_at.strftime('%Y-%m')

        month_departures = [
            item for item in application.TourSchedule.query.all()
            if item.starts_at.strftime('%Y-%m') == target_month
        ]
        # Seeded catalogue departures can share this month, so the expected
        # totals are read from the schedules instead of assuming one fixture.
        expected_capacity = sum(item.capacity for item in month_departures)
        expected_seats = sum(item.booked_count for item in month_departures)

    try:
        response = admin.get('/api/admin/operations')
        assert response.status_code == 200
        analytics = response.get_json()['analytics']
        funnel = {stage['label']: stage for stage in analytics['funnel']}
        assert funnel['Unique visitors']['count'] == 1
        assert funnel['Booking page visitors']['count'] == 1
        assert funnel['Booking requests']['count'] == 1
        assert funnel['Paid bookings']['count'] == 1
        source = next(row for row in analytics['traffic_sources'] if row['source'] == 'Instagram')
        assert source['visitors'] == 1
        assert source['booking_requests'] == 1
        assert source['paid_revenue'] == 12000
        occupancy = next(row for row in analytics['occupancy_trends'] if row['month'] == target_month)
        assert occupancy['capacity'] == expected_capacity
        assert occupancy['booked_seats'] == expected_seats
        assert occupancy['occupancy_rate'] == round(expected_seats / expected_capacity * 100, 1)
        property_row = next(row for row in analytics['property_revenue'] if row['slug'] == property_slug)
        assert property_row['paid_bookings'] == 1
        assert property_row['paid_revenue'] == 12000
        with application.app.app_context():
            event = application.AnalyticsEvent.query.filter_by(visitor_key=visitor_key).first()
            assert event is not None
            assert event.visitor_key != visitor_token
    finally:
        with application.app.app_context():
            application.AnalyticsEvent.query.filter_by(visitor_key=visitor_key).delete()
            application.Booking.query.filter_by(tour=property_slug).delete()
            application.TourSchedule.query.filter_by(tour_slug=tour_slug).delete()
            application.Property.query.filter_by(slug=property_slug).delete()
            application.Tour.query.filter_by(slug=tour_slug).delete()
            application.db.session.commit()


def test_admin_pages_and_catalogue_api_require_sign_in():
    client = application.app.test_client()

    assert client.get('/admin').status_code == 302
    assert client.get('/dashboard').status_code == 302
    assert client.get('/api/admin/catalogue').status_code == 401
    assert client.get('/api/admin/dashboard').status_code == 401


def test_admin_can_create_update_and_delete_tours(admin_client):
    client, headers = admin_client
    response = client.post('/api/admin/tours', json={
        'name': 'Test Sunset Sailing',
        'description': 'A test catalog tour.',
        'duration': 'Two hours',
        'price': 1200,
        'image_url': 'images/shela-village.webp',
    }, headers=headers)

    assert response.status_code == 201
    tour = response.get_json()['tour']
    assert tour['slug'] == 'test-sunset-sailing'
    assert application.calculate_booking_price(tour['slug'], 2) == 2400
    assert tour['slug'] in {item['slug'] for item in client.get('/api/catalogue').get_json()['tours']}

    response = client.put(f"/api/admin/tours/{tour['slug']}", json={
        'name': 'Updated Sunset Sailing',
        'description': 'Updated description.',
        'duration': 'Three hours',
        'price': 1500,
        'image_url': '',
    }, headers=headers)
    assert response.status_code == 200
    assert application.calculate_booking_price(tour['slug'], 2) == 3000

    assert client.delete(f"/api/admin/tours/{tour['slug']}", headers=headers).status_code == 204
    with pytest.raises(ValueError):
        application.calculate_booking_price(tour['slug'], 1)


def test_property_reviews_are_attached_to_the_selected_property(admin_client):
    client, headers = admin_client
    response = client.post('/api/admin/properties', json={
        'name': 'Test Shela Retreat',
        'property_type': 'apartment',
        'location': 'Shela',
        'price_per_night': 7000,
        'guests': 4,
        'amenities': ['Wi-Fi', 'Beach access'],
        'latitude': -2.29,
        'longitude': 40.91,
        'image_url': 'pictures/187747945.jpg',
        'description': 'A test property.',
    }, headers=headers)
    assert response.status_code == 201
    listing = response.get_json()['property']
    assert listing['amenities'] == ['Wi-Fi', 'Beach access']
    assert listing['latitude'] == -2.29
    assert listing['longitude'] == 40.91
    assert application.calculate_booking_price(listing['slug'], 2) == 14000

    invalid_coordinates = client.put(f"/api/admin/properties/{listing['id']}", json={
        'name': 'Test Shela Retreat',
        'property_type': 'apartment',
        'location': 'Shela',
        'price_per_night': 7000,
        'guests': 4,
        'latitude': -2.29,
        'longitude': 200,
        'image_url': 'pictures/187747945.jpg',
        'description': 'A test property.',
    }, headers=headers)
    assert invalid_coordinates.status_code == 400

    # Reviews are written by customers from their bookings, so seed one directly
    # to check that removing the listing also removes its published reviews.
    with application.app.app_context():
        application.db.session.add(application.Review(
            reviewer_name='Guest',
            reviewer_email='guest@example.test',
            place=listing['name'],
            target_type='property',
            target_id=listing['slug'],
            rating=5,
            comment='Lovely stay.',
        ))
        application.db.session.commit()

    assert len(client.get('/reviews?target_type=property&target_id=' + listing['slug']).get_json()['reviews']) == 1
    assert client.get('/reviews?target_type=tour&target_id=' + listing['slug']).get_json()['reviews'] == []

    assert client.delete(f"/api/admin/properties/{listing['id']}", headers=headers).status_code == 204
    assert client.get('/reviews?target_type=property&target_id=' + listing['slug']).get_json()['reviews'] == []


def test_admin_can_save_geocoded_beach_and_heritage_destinations(admin_client):
    from uuid import uuid4

    client, headers = admin_client
    name = f'Coordinate Test Landmark {uuid4().hex}'
    response = client.post('/api/admin/destinations', json={
        'name': name,
        'search_location': 'Shela',
        'site_type': 'beach',
        'latitude': -2.29,
        'longitude': 40.91,
        'description': 'A test landmark used for proximity search.',
    }, headers=headers)

    assert response.status_code == 201
    destination = response.get_json()['destination']
    assert destination['site_type'] == 'beach'
    assert destination['latitude'] == -2.29
    assert destination['longitude'] == 40.91

    response = client.put(f"/api/admin/destinations/{destination['slug']}", json={
        'name': name,
        'search_location': 'Lamu Old Town',
        'site_type': 'heritage',
        'latitude': -2.27,
        'longitude': 40.90,
        'description': 'An updated test landmark.',
    }, headers=headers)
    assert response.status_code == 200
    assert response.get_json()['destination']['site_type'] == 'heritage'

    invalid = client.put(f"/api/admin/destinations/{destination['slug']}", json={
        'name': name,
        'search_location': 'Lamu Old Town',
        'site_type': 'heritage',
        'latitude': -2.27,
        'longitude': 200,
        'description': 'An invalid test landmark.',
    }, headers=headers)
    assert invalid.status_code == 400
    assert client.delete(f"/api/admin/destinations/{destination['slug']}", headers=headers).status_code == 204


def test_admin_can_manage_trending_destinations_and_other_admin_accounts(admin_client):
    client, headers = admin_client
    response = client.post('/api/admin/destinations', json={
        'name': 'Test Coast',
        'description': 'A destination for testing.',
        'image_url': 'pictures/187168867.jpg',
        'search_location': 'Test Coast',
    }, headers=headers)
    assert response.status_code == 201
    destination = response.get_json()['destination']
    assert destination in client.get('/api/catalogue').get_json()['destinations']

    response = client.put(f"/api/admin/destinations/{destination['slug']}", json={
        **destination,
        'description': 'Updated destination.',
    }, headers=headers)
    assert response.status_code == 200
    assert response.get_json()['destination']['description'] == 'Updated destination.'

    response = client.post('/api/admin/admins', json={
        'name': 'Second Admin',
        'email': f"second-{uuid.uuid4().hex}@example.test",
        'password': 'a-long-test-password',
    }, headers=headers)
    assert response.status_code == 201
    created_admin = response.get_json()['admin']
    with application.app.app_context():
        admin = application.db.session.get(application.AdminAccount, created_admin['id'])
        assert admin.password_hash != 'a-long-test-password'

    assert client.delete(f"/api/admin/destinations/{destination['slug']}", headers=headers).status_code == 204
    assert client.delete(f"/api/admin/admins/{created_admin['id']}", headers=headers).status_code == 204


def test_hospitality_page_is_removed_and_catalog_is_public():
    response = application.app.test_client().get('/hospitality.html')

    assert response.status_code == 404
    assert not application.os.path.exists(application.os.path.join(application.BASE_DIR, 'hospitality.html'))
    catalogue = application.app.test_client().get('/api/catalogue').get_json()
    assert catalogue['tours']
    assert catalogue['properties']
    assert catalogue['destinations']


def test_reviews_require_a_booking_and_are_read_only_for_visitors():
    public_client = application.app.test_client()

    response = public_client.post('/review-submit', json={
        'rating': 5,
        'comment': 'Unattached review.',
        'target_type': 'tour',
        'target_id': 'not-a-real-tour',
    })

    assert response.status_code == 401
    reviews = public_client.get('/reviews?target_type=tour&target_id=not-a-real-tour')
    assert reviews.status_code == 200
    assert reviews.get_json()['reviews'] == []


def test_admin_mutations_require_csrf(admin_client):
    client, _ = admin_client

    response = client.post('/api/admin/tours', json={
        'name': 'No CSRF',
        'description': 'Should not be created.',
        'duration': 'One hour',
        'price': 1000,
    })

    assert response.status_code == 403


def test_admin_can_publish_and_remove_tour_availability(admin_client):
    client, headers = admin_client
    tour_response = client.post('/api/admin/tours', json={
        'name': 'Availability Test Tour',
        'description': 'A tour to test schedule management.',
        'duration': 'Two hours',
        'price': 1000,
    }, headers=headers)
    assert tour_response.status_code == 201
    slug = tour_response.get_json()['tour']['slug']
    starts_at = (datetime.now(ZoneInfo('Africa/Nairobi')).replace(tzinfo=None) + timedelta(days=5)).replace(second=0, microsecond=0)

    response = client.post('/api/admin/availability', json={
        'tour_slug': slug,
        'starts_at': starts_at.isoformat(timespec='minutes'),
        'capacity': 8,
    }, headers=headers)
    assert response.status_code == 201
    schedule = response.get_json()['schedule']
    assert schedule['capacity'] == 8
    assert schedule['remaining'] == 8
    assert schedule in client.get('/api/admin/availability').get_json()['schedules']

    response = client.put(f"/api/admin/availability/{schedule['id']}", json={
        'capacity': 12,
        'starts_at': starts_at.isoformat(timespec='minutes'),
    }, headers=headers)
    assert response.status_code == 200
    assert response.get_json()['schedule']['capacity'] == 12
    assert client.delete(f"/api/admin/availability/{schedule['id']}", headers=headers).status_code == 204
    assert client.delete(f'/api/admin/tours/{slug}', headers=headers).status_code == 204


def test_admin_dashboard_data_contains_summary_and_recent_activity(admin_client):
    client, _ = admin_client
    response = client.get('/api/admin/dashboard')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['total_submissions'] >= len(payload['recent_submissions'])
    assert payload['total_bookings'] >= len(payload['recent_bookings'])
    assert len(payload['recent_submissions']) <= 20
    assert len(payload['recent_bookings']) <= 20
    assert payload['csrf_token']
    assert client.post('/admin/logout', headers={
        'X-CSRF-Token': payload['csrf_token'],
        'Accept': 'application/json',
    }).status_code == 204
    assert client.get('/api/admin/dashboard').status_code == 401


def test_vendor_registration_requires_csrf_and_a_twelve_character_password():
    client = application.app.test_client()
    data = {
        'name': 'New Lamu Vendor',
        'email': f'new-vendor-{uuid.uuid4().hex}@example.test',
        'password': 'short',
    }

    assert client.post('/vendor/register', json=data).status_code == 403
    token_response = client.get('/api/vendor/registration-token')
    assert token_response.status_code == 200
    headers = {'X-CSRF-Token': token_response.get_json()['csrf_token']}
    assert client.post('/vendor/register', json=data, headers=headers).status_code == 400

    data['password'] = 'pass-1234567'
    response = client.post('/vendor/register', json=data, headers=headers)
    assert response.status_code == 201
    vendor_data = response.get_json()['vendor']
    assert vendor_data['email'] == data['email']
    assert client.get('/api/vendor/catalogue').get_json()['vendor']['id'] == vendor_data['id']

    with application.app.app_context():
        vendor = application.db.session.get(application.VendorAccount, vendor_data['id'])
        assert vendor.password_hash != data['password']
        application.db.session.delete(vendor)
        application.db.session.commit()


def test_vendor_can_manage_only_their_own_tours_and_properties(vendor_pair):
    first, second = vendor_pair
    first_client, first_headers, first_id = first
    second_client, second_headers, _ = second

    tour_response = first_client.post('/api/vendor/tours', json={
        'name': f'Vendor {first_id} Sailing',
        'description': 'A vendor-owned sailing experience.',
        'duration': 'Two hours',
        'price': 1800,
    }, headers=first_headers)
    property_response = first_client.post('/api/vendor/properties', json={
        'name': f'Vendor {first_id} Hostel',
        'property_type': 'hostel',
        'location': 'Shela',
        'price_per_night': 6000,
        'guests': 3,
        'description': 'A vendor-owned hostel.',
    }, headers=first_headers)
    assert tour_response.status_code == 201
    assert property_response.status_code == 201
    tour = tour_response.get_json()['tour']
    listing = property_response.get_json()['property']

    assert [item['slug'] for item in first_client.get('/api/vendor/catalogue').get_json()['tours']] == [tour['slug']]
    assert second_client.get('/api/vendor/catalogue').get_json()['tours'] == []
    assert second_client.put(f"/api/vendor/tours/{tour['slug']}", json=tour, headers=second_headers).status_code == 404
    assert second_client.delete(f"/api/vendor/properties/{listing['id']}", headers=second_headers).status_code == 404

    updated_tour = {
        **tour,
        'name': 'Updated vendor sailing',
        'price': 2200,
    }
    assert first_client.put(f"/api/vendor/tours/{tour['slug']}", json=updated_tour, headers=first_headers).status_code == 200
    assert first_client.delete(f"/api/vendor/tours/{tour['slug']}", headers=first_headers).status_code == 204
    assert first_client.delete(f"/api/vendor/properties/{listing['id']}", headers=first_headers).status_code == 204
    assert first_client.post('/vendor/logout', headers=first_headers).status_code == 204
    assert first_client.get('/api/vendor/catalogue').status_code == 401


def test_admin_can_remove_vendor_account_and_owned_listings(admin_client, vendor_pair):
    admin, admin_headers = admin_client
    vendor_client, vendor_headers, vendor_id = vendor_pair[0]
    response = vendor_client.post('/api/vendor/tours', json={
        'name': 'Vendor Deletion Test Tour',
        'description': 'A listing used to verify vendor removal.',
        'duration': 'One hour',
        'price': 1000,
    }, headers=vendor_headers)
    assert response.status_code == 201
    slug = response.get_json()['tour']['slug']

    response = admin.delete(f'/api/admin/vendors/{vendor_id}', headers=admin_headers)
    assert response.status_code == 204
    public_tours = application.app.test_client().get('/api/catalogue').get_json()['tours']
    assert slug not in {tour['slug'] for tour in public_tours}
    with application.app.app_context():
        assert application.db.session.get(application.VendorAccount, vendor_id) is None
        assert application.db.session.get(application.Tour, slug) is None


def test_vendor_can_view_and_advance_only_their_tour_bookings(monkeypatch, vendor_pair):
    first_client, first_headers, vendor_id = vendor_pair[0]
    second_client, second_headers, _ = vendor_pair[1]
    monkeypatch.setattr(application, 'send_booking_status_notification', lambda booking: True)
    starts_at = (datetime.now(ZoneInfo('Africa/Nairobi')).replace(tzinfo=None) + timedelta(days=7)).replace(second=0, microsecond=0)
    with application.app.app_context():
        tour = application.Tour(
            slug=f'vendor-booking-{vendor_id}',
            vendor_id=vendor_id,
            name='Vendor Booking Tour',
            description='A vendor booking workflow test.',
            duration='Two hours',
            price=1200,
        )
        schedule = application.TourSchedule(tour_slug=tour.slug, starts_at=starts_at, capacity=5, booked_count=2)
        application.db.session.add_all([tour, schedule])
        application.db.session.flush()
        booking = application.Booking(
            tour=tour.slug,
            schedule_id=schedule.id,
            name='Test Guest',
            email='test-guest@example.test',
            phone='+254712345678',
            date=starts_at.date().isoformat(),
            time=starts_at.strftime('%H:%M'),
            guests=2,
            amount=2400,
            payment_status='pending',
            status='requested',
        )
        application.db.session.add(booking)
        application.db.session.commit()
        booking_id, schedule_id = booking.id, schedule.id

    assert [item['id'] for item in first_client.get('/api/vendor/bookings').get_json()['bookings']] == [booking_id]
    assert second_client.get('/api/vendor/bookings').get_json()['bookings'] == []
    assert second_client.post(
        f'/api/vendor/bookings/{booking_id}/status',
        json={'status': 'confirmed'},
        headers=second_headers,
    ).status_code == 404
    assert first_client.post(
        f'/api/vendor/bookings/{booking_id}/status',
        json={'status': 'confirmed'},
        headers=first_headers,
    ).status_code == 409
    with application.app.app_context():
        application.db.session.get(application.Booking, booking_id).payment_status = 'paid'
        application.db.session.commit()

    for status in ('confirmed', 'in_preparation', 'completed'):
        response = first_client.post(
            f'/api/vendor/bookings/{booking_id}/status',
            json={'status': status},
            headers=first_headers,
        )
        assert response.status_code == 200
        assert response.get_json()['booking']['status'] == status
        assert response.get_json()['email_sent'] is True

    assert first_client.post(
        f'/api/vendor/bookings/{booking_id}/status',
        json={'status': 'cancelled'},
        headers=first_headers,
    ).status_code == 409
    with application.app.app_context():
        assert application.db.session.get(application.TourSchedule, schedule_id).booked_count == 2
        tour = application.db.session.get(application.Tour, f'vendor-booking-{vendor_id}')
        cancelled_schedule = application.TourSchedule(
            tour_slug=tour.slug,
            starts_at=starts_at + timedelta(days=1),
            capacity=3,
            booked_count=1,
        )
        application.db.session.add(cancelled_schedule)
        application.db.session.flush()
        cancelled_booking = application.Booking(
            tour=tour.slug,
            schedule_id=cancelled_schedule.id,
            name='Second Test Guest',
            email='second-guest@example.test',
            phone='+254700000000',
            date=cancelled_schedule.starts_at.date().isoformat(),
            time=cancelled_schedule.starts_at.strftime('%H:%M'),
            guests=1,
            amount=1200,
            payment_status='pending',
            status='requested',
        )
        application.db.session.add(cancelled_booking)
        application.db.session.commit()
        cancelled_booking_id, cancelled_schedule_id = cancelled_booking.id, cancelled_schedule.id

    cancelled_response = first_client.post(
        f'/api/vendor/bookings/{cancelled_booking_id}/status',
        json={'status': 'cancelled'},
        headers=first_headers,
    )
    assert cancelled_response.status_code == 409
    assert 'M-Pesa request' in cancelled_response.get_json()['error']
    with application.app.app_context():
        assert application.db.session.get(application.TourSchedule, cancelled_schedule_id).booked_count == 1


def test_vendor_image_upload_checks_role_csrf_and_image_signature(tmp_path, monkeypatch, vendor_pair):
    client, headers, vendor_id = vendor_pair[0]
    monkeypatch.setattr(application, 'BASE_DIR', str(tmp_path))
    image = b'\x89PNG\r\n\x1a\n' + b'test-image-data'

    assert application.app.test_client().post('/api/vendor/uploads').status_code == 401
    assert client.post('/api/vendor/uploads', data={
        'image': (io.BytesIO(image), 'cover.png'),
    }, content_type='multipart/form-data').status_code == 403

    response = client.post('/api/vendor/uploads', data={
        'image': (io.BytesIO(b'not an image'), 'cover.png'),
    }, headers=headers, content_type='multipart/form-data')
    assert response.status_code == 400

    response = client.post('/api/vendor/uploads', data={
        'image': (io.BytesIO(image), 'cover.png'),
    }, headers=headers, content_type='multipart/form-data')
    assert response.status_code == 201
    image_url = response.get_json()['image_url']
    assert image_url.startswith(f'uploads/vendors/{vendor_id}/')
    assert client.get(f'/{image_url}').data == image


def test_frontend_routes_serve_the_built_react_app(tmp_path, monkeypatch, admin_client):
    dist = tmp_path / 'dist'
    assets = dist / 'assets'
    assets.mkdir(parents=True)
    (dist / 'index.html').write_text('<div id="root">React app</div>', encoding='utf-8')
    (assets / 'main.js').write_text('console.log("React");', encoding='utf-8')
    monkeypatch.setattr(application, 'FRONTEND_DIST', str(dist))

    client, _ = admin_client

    assert b'React app' in client.get('/').data
    assert b'React app' in client.get('/tours.html').data
    assert b'React app' in client.get('/login').data
    assert b'React app' in client.get('/admin/login').data
    assert b'React app' in client.get('/dashboard').data
    assert b'React app' in client.get('/vendor/login').data
    assert b'React app' in client.get('/vendor/register').data
    assert b'React app' in client.get('/partner/login').data
    assert b'React app' in client.get('/partner/register').data
    for page in (
        '/properties.html',
        '/explore.html',
        '/safari-operators.html',
        '/destinations.html',
        '/blog.html',
        '/blog/when-to-visit-kenya',
        '/gallery.html',
        '/reviews.html',
        '/compare.html',
        '/wishlist.html',
        '/faq.html',
        '/how-it-works.html',
        '/booking-guide.html',
        '/cancellation-policy.html',
        '/privacy-policy.html',
        '/terms.html',
    ):
        assert b'React app' in client.get(page).data, page
    assert b'console.log("React")' in client.get('/assets/main.js').data


def test_partner_portal_routes_use_the_partner_session(tmp_path, monkeypatch):
    dist = tmp_path / 'dist'
    dist.mkdir()
    (dist / 'index.html').write_text('<div id="root">React app</div>', encoding='utf-8')
    monkeypatch.setattr(application, 'FRONTEND_DIST', str(dist))

    email = f'partner-{uuid.uuid4().hex}@example.test'
    with application.app.app_context():
        vendor = application.VendorAccount(
            name='Partner Alias',
            email=email,
            password_hash=application.generate_password_hash('partner-alias-password'),
        )
        application.db.session.add(vendor)
        application.db.session.commit()
        vendor_id = vendor.id

    client = application.app.test_client()
    try:
        failed = client.post('/partner/login', data={'email': email, 'password': 'wrong-password'})
        assert failed.status_code == 302
        assert failed.headers['Location'].startswith('/partner/login?error=')

        signed_in = client.post('/partner/login', data={'email': email, 'password': 'partner-alias-password'})
        assert signed_in.status_code == 302
        assert signed_in.headers['Location'].endswith('/partner/dashboard')
        with client.session_transaction() as session:
            csrf_token = session['vendor_csrf']

        assert b'React app' in client.get('/partner/dashboard').data
        assert client.post('/partner/logout', headers={'X-CSRF-Token': csrf_token}).status_code == 204

        anonymous = client.get('/partner/dashboard')
        assert anonymous.status_code == 302
        assert anonymous.headers['Location'].endswith('/partner/login')
    finally:
        with application.app.app_context():
            vendor = application.db.session.get(application.VendorAccount, vendor_id)
            if vendor:
                application.db.session.delete(vendor)
                application.db.session.commit()


def test_contact_form_accepts_json_for_the_react_frontend(monkeypatch):
    monkeypatch.setattr(application, 'send_email_notification', lambda submission: False)
    client = application.app.test_client()

    response = client.post('/contact-submit', json={
        'name': 'React visitor',
        'email': 'visitor@example.test',
        'subject': 'A Lamu question',
        'message': 'I would like to learn more about the tours.',
    })

    assert response.status_code == 201
    assert response.get_json() == {
        'message': 'Your message has been received.',
        'email_sent': False,
    }


def test_admin_counts_newsletter_subscribers(admin_client):
    client, _ = admin_client
    email = f'admin-newsletter-{uuid.uuid4().hex[:10]}@example.test'
    try:
        signup = client.post('/api/newsletter', json={'email': email, 'source': 'footer'})
        assert signup.status_code == 201

        data = client.get('/api/admin/catalogue').get_json()
        assert data['newsletter']['count'] >= 1
        assert any(item['email'] == email for item in data['newsletter']['recent'])
    finally:
        with application.app.app_context():
            application.NewsletterSubscriber.query.filter_by(email=email).delete()
            application.db.session.commit()


@pytest.mark.parametrize('property_type', ['hotel', 'lodge', 'resort', 'apartment', 'rental', 'hostel'])
def test_admin_accepts_each_accommodation_type(admin_client, property_type):
    client, headers = admin_client
    response = client.post('/api/admin/properties', json={
        'name': f'Test {property_type.title()} Listing',
        'property_type': property_type,
        'location': 'Lamu',
        'price_per_night': 5000,
        'guests': 2,
        'description': 'A listing used to verify the accommodation vocabulary.',
    }, headers=headers)

    assert response.status_code == 201
    listing = response.get_json()['property']
    assert listing['property_type'] == property_type
    assert client.delete(f"/api/admin/properties/{listing['id']}", headers=headers).status_code == 204


@pytest.mark.parametrize('legacy_type', ['villa', 'guest house', 'home'])
def test_legacy_accommodation_types_are_saved_as_rentals(admin_client, legacy_type):
    client, headers = admin_client
    response = client.post('/api/admin/properties', json={
        'name': f'Test Legacy {legacy_type.title()}',
        'property_type': legacy_type,
        'location': 'Lamu',
        'price_per_night': 5000,
        'guests': 2,
        'description': 'A listing created with an older accommodation type.',
    }, headers=headers)

    assert response.status_code == 201
    listing = response.get_json()['property']
    assert listing['property_type'] == 'rental'
    assert client.delete(f"/api/admin/properties/{listing['id']}", headers=headers).status_code == 204


def test_catalogue_ships_multi_day_safari_packages():
    catalogue = application.app.test_client().get('/api/catalogue').get_json()
    packages = [tour for tour in catalogue['tours'] if tour['tour_type'] == 'multi-day-safari']

    assert packages
    assert all(tour['duration_days'] >= 2 for tour in packages)
    with application.app.app_context():
        for tour in packages:
            departures = application.TourSchedule.query.filter_by(tour_slug=tour['slug'], is_active=True).all()
            assert departures, tour['slug']


def test_catalogue_ships_every_browsable_region_destination():
    catalogue = application.app.test_client().get('/api/catalogue').get_json()
    destinations = {destination['slug'] for destination in catalogue['destinations']}

    assert {
        'nairobi', 'naivasha', 'maasai-mara', 'amboseli', 'tsavo',
        'mount-kenya', 'mombasa', 'diani', 'lamu', 'watamu',
    } <= destinations
    tour_destinations = {tour['destination'] for tour in catalogue['tours']}
    stay_destinations = {stay['destination'] for stay in catalogue['properties']}
    for slug in ('tsavo', 'mount-kenya'):
        assert slug in tour_destinations, slug
        assert slug in stay_destinations, slug


def test_unknown_accommodation_type_is_rejected(admin_client):
    client, headers = admin_client
    response = client.post('/api/admin/properties', json={
        'name': 'Test Treehouse',
        'property_type': 'treehouse',
        'location': 'Lamu',
        'price_per_night': 5000,
        'guests': 2,
        'description': 'A listing that uses an unsupported accommodation type.',
    }, headers=headers)

    assert response.status_code == 400
    assert 'type' in response.get_json()['error']


def test_existing_legacy_listings_are_migrated_on_startup():
    token = uuid.uuid4().hex
    with application.app.app_context():
        listing = application.Property(
            slug=f'legacy-stay-{token}',
            owner_name='Legacy owner',
            owner_email=f'{token}@example.test',
            name='Legacy Guest House',
            property_type='guest house',
            location='Lamu',
            price_per_night=4500,
            guests=2,
            description='A listing saved before the accommodation vocabulary existed.',
        )
        application.db.session.add(listing)
        application.db.session.commit()

        application.ensure_catalog_columns()
        application.db.session.refresh(listing)
        assert listing.property_type == 'rental'

        application.db.session.delete(listing)
        application.db.session.commit()


def test_admin_promotions_are_labelled_tracked_and_removable(admin_client):
    """A paid placement is labelled publicly, counted, and easy to end."""
    client, headers = admin_client
    today = datetime.now(application.KENYA_TIMEZONE).date()
    payload = {
        'listing_type': 'tour',
        'listing_slug': 'tsavo-game-drive',
        'tier': 'spotlight',
        'headline': 'Red elephants',
        'starts_on': today.isoformat(),
        'ends_on': (today + timedelta(days=7)).isoformat(),
    }

    response = client.post('/api/admin/promotions', json=payload, headers=headers)
    assert response.status_code == 201
    promotion = response.get_json()['promotion']
    assert promotion['tier'] == 'spotlight'
    assert promotion['rank'] == 2
    assert promotion['listing_name'] == 'Tsavo Red-Elephant Safari'

    catalogue = client.get('/api/catalogue').get_json()
    tour = next(item for item in catalogue['tours'] if item['slug'] == 'tsavo-game-drive')
    assert tour['promotion']['sponsored'] is True
    assert tour['promotion']['label'] == 'Red elephants'

    search = client.get('/api/search', query_string={'q': 'tsavo'}).get_json()
    assert search['results'][0]['slug'] == 'tsavo-game-drive'
    assert search['results'][0]['promotion']['sponsored'] is True

    assert client.post('/api/promotions/tour/tsavo-game-drive/click').status_code == 204
    assert client.post('/api/promotions/tour/not-a-tour/click').status_code == 204
    assert client.post('/api/promotions/service/anything/click').status_code == 400

    admin_view = client.get('/api/admin/catalogue').get_json()
    saved = next(item for item in admin_view['promotions'] if item['listing_slug'] == 'tsavo-game-drive')
    assert saved['clicks'] == 1
    assert saved['impressions'] >= 1
    assert admin_view['promotion_max_active'] == 6

    assert client.delete(f"/api/admin/promotions/{saved['id']}", headers=headers).status_code == 204
    catalogue = client.get('/api/catalogue').get_json()
    tour = next(item for item in catalogue['tours'] if item['slug'] == 'tsavo-game-drive')
    assert tour['promotion'] is None


def test_promotions_require_csrf_a_published_listing_and_a_valid_window(admin_client):
    client, headers = admin_client
    payload = {
        'listing_type': 'tour',
        'listing_slug': 'tsavo-game-drive',
        'tier': 'featured',
        'starts_on': '2026-01-10',
        'ends_on': '2026-01-20',
    }

    assert client.post('/api/admin/promotions', json=payload).status_code == 403
    assert client.post(
        '/api/admin/promotions',
        json={**payload, 'listing_slug': 'missing-listing'},
        headers=headers,
    ).status_code == 400
    assert client.post(
        '/api/admin/promotions',
        json={**payload, 'ends_on': '2026-01-01'},
        headers=headers,
    ).status_code == 400
    assert client.post(
        '/api/admin/promotions',
        json={**payload, 'starts_on': 'not-a-date'},
        headers=headers,
    ).status_code == 400
