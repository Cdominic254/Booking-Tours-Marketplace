"""Guest reviews: public reading and rating summaries, account-only writing."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import uuid

import pytest

import app as application

KENYA_TIMEZONE = ZoneInfo('Africa/Nairobi')
PASSWORD = 'review-test-password'


def today_in_kenya():
    return datetime.now(KENYA_TIMEZONE).date()


def days_ago(days):
    return (today_in_kenya() - timedelta(days=days)).isoformat()


def days_ahead(days):
    return (today_in_kenya() + timedelta(days=days)).isoformat()


@pytest.fixture
def review_site():
    """Two customer accounts, one tour and one accommodation listing to review."""
    tour_slug = f'review-tour-{uuid.uuid4().hex[:10]}'
    property_slug = f'review-stay-{uuid.uuid4().hex[:10]}'
    emails = [f'review-{label}-{uuid.uuid4().hex}@example.test' for label in ('guest', 'stranger')]
    with application.app.app_context():
        users = [
            application.User(
                name='Review Guest' if index == 0 else 'Review Stranger',
                email=email,
                password_hash=application.generate_password_hash(PASSWORD),
            )
            for index, email in enumerate(emails)
        ]
        tour = application.Tour(
            slug=tour_slug,
            name='Review Test Dhow Sunset',
            description='A tour used to test guest reviews.',
            duration='Two hours',
            price=2500,
            category='Dhow & Island Hopping',
        )
        listing = application.Property(
            slug=property_slug,
            owner_name='Review Test Owner',
            owner_email='review-owner@example.test',
            name='Review Test Beach House',
            property_type='villa',
            location='Shela',
            price_per_night=9000,
            guests=4,
            description='An accommodation used to test guest reviews.',
            image_url='pictures/187747945.jpg',
        )
        application.db.session.add_all([*users, tour, listing])
        application.db.session.commit()
        user_ids = [user.id for user in users]
        property_id = listing.id

    clients = []
    for email in emails:
        client = application.app.test_client()
        response = client.post('/login', data={'email': email, 'password': PASSWORD})
        assert response.status_code == 302
        with client.session_transaction() as session:
            csrf_token = session['customer_csrf']
        clients.append({'client': client, 'csrf': csrf_token, 'email': email})

    yield {
        'guest': clients[0],
        'stranger': clients[1],
        'guest_id': user_ids[0],
        'stranger_id': user_ids[1],
        'tour_slug': tour_slug,
        'property_slug': property_slug,
        'property_id': property_id,
        'user_ids': user_ids,
    }

    with application.app.app_context():
        application.Review.query.filter(
            application.Review.target_id.in_([tour_slug, property_slug])
        ).delete(synchronize_session=False)
        application.Booking.query.filter(
            application.Booking.user_id.in_(user_ids)
        ).delete(synchronize_session=False)
        application.db.session.delete(application.db.session.get(application.Tour, tour_slug))
        listing = application.db.session.get(application.Property, property_id)
        if listing:
            application.db.session.delete(listing)
        for user_id in user_ids:
            user = application.db.session.get(application.User, user_id)
            if user:
                application.db.session.delete(user)
        application.db.session.commit()


def make_booking(user_id, tour, **overrides):
    """Store a booking directly so each review rule can be exercised in isolation."""
    values = {
        'user_id': user_id,
        'name': 'Review Guest',
        'email': 'review-guest@example.test',
        'phone': '+254712345678',
        'tour': tour,
        'date': days_ago(2),
        'time': '09:00',
        'guests': 1,
        'amount': 2500,
        'payment_status': 'paid',
        'status': 'confirmed',
    }
    values.update(overrides)
    with application.app.app_context():
        booking = application.Booking(**values)
        application.db.session.add(booking)
        application.db.session.commit()
        return booking.id


def post_review(account, csrf_token=True, **payload):
    headers = {'Accept': 'application/json'}
    if csrf_token:
        headers['X-CSRF-Token'] = account['csrf']
    return account['client'].post('/review-submit', json=payload, headers=headers)


def test_anonymous_visitors_can_read_but_not_write_reviews(review_site):
    anonymous = application.app.test_client()

    listing_reviews = anonymous.get(
        f"/reviews?target_type=tour&target_id={review_site['tour_slug']}"
    )
    submission = anonymous.post('/review-submit', json={
        'booking_id': 1,
        'rating': 5,
        'comment': 'Written without signing in.',
    })

    assert listing_reviews.status_code == 200
    assert listing_reviews.get_json()['reviews'] == []
    assert listing_reviews.get_json()['summary'] == {'rating': 0, 'review_count': 0}
    assert submission.status_code == 401


def test_signed_in_customers_need_a_csrf_token_to_publish(review_site):
    booking_id = make_booking(review_site['guest_id'], review_site['tour_slug'])

    response = post_review(
        review_site['guest'],
        csrf_token=False,
        booking_id=booking_id,
        rating=5,
        comment='A review without a CSRF token.',
    )

    assert response.status_code == 403


def test_customer_reviews_a_paid_booking_that_already_happened(review_site):
    booking_id = make_booking(review_site['guest_id'], review_site['tour_slug'])

    response = post_review(
        review_site['guest'],
        booking_id=booking_id,
        rating=5,
        comment='The dhow sunset was the highlight of our trip.',
    )

    assert response.status_code == 201
    review = response.get_json()['review']
    assert review['booking_id'] == booking_id
    assert review['target_type'] == 'tour'
    assert review['target_id'] == review_site['tour_slug']
    assert review['place'] == 'Review Test Dhow Sunset'
    assert review['reviewer_name'] == 'Review Guest'
    assert review['rating'] == 5

    listed = review_site['guest']['client'].get(
        f"/reviews?target_type=tour&target_id={review_site['tour_slug']}"
    ).get_json()
    assert len(listed['reviews']) == 1
    assert listed['summary'] == {'rating': 5.0, 'review_count': 1}

    catalogue = review_site['guest']['client'].get('/api/catalogue').get_json()
    tour = next(item for item in catalogue['tours'] if item['slug'] == review_site['tour_slug'])
    assert tour['rating'] == 5.0
    assert tour['review_count'] == 1


def test_one_review_per_booking(review_site):
    booking_id = make_booking(review_site['guest_id'], review_site['tour_slug'])
    first = post_review(
        review_site['guest'],
        booking_id=booking_id,
        rating=4,
        comment='Lovely afternoon on the water.',
    )

    second = post_review(
        review_site['guest'],
        booking_id=booking_id,
        rating=5,
        comment='Trying to review the same booking twice.',
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_completed_bookings_can_be_reviewed_before_the_date_passes(review_site):
    booking_id = make_booking(
        review_site['guest_id'],
        review_site['tour_slug'],
        date=days_ahead(3),
        status='completed',
    )

    response = post_review(
        review_site['guest'],
        booking_id=booking_id,
        rating=5,
        comment='The operator marked this trip as completed.',
    )

    assert response.status_code == 201


def test_upcoming_paid_bookings_cannot_be_reviewed(review_site):
    booking_id = make_booking(
        review_site['guest_id'],
        review_site['tour_slug'],
        date=days_ahead(4),
    )

    response = post_review(
        review_site['guest'],
        booking_id=booking_id,
        rating=5,
        comment='Reviewing a trip that has not happened yet.',
    )

    assert response.status_code == 409
    assert 'once the experience or stay is over' in response.get_json()['error']


@pytest.mark.parametrize('overrides', [
    {'payment_status': 'pending', 'status': 'requested'},
    {'payment_status': 'failed', 'status': 'cancelled'},
    {'payment_status': 'paid', 'status': 'cancelled'},
])
def test_unpaid_and_cancelled_bookings_cannot_be_reviewed(review_site, overrides):
    booking_id = make_booking(review_site['guest_id'], review_site['tour_slug'], **overrides)

    response = post_review(
        review_site['guest'],
        booking_id=booking_id,
        rating=3,
        comment='Reviewing a booking that was never served.',
    )

    assert response.status_code == 409
    assert 'Only paid bookings that were used can be reviewed.' in response.get_json()['error']


def test_customers_cannot_review_someone_elses_booking(review_site):
    booking_id = make_booking(review_site['guest_id'], review_site['tour_slug'])

    response = post_review(
        review_site['stranger'],
        booking_id=booking_id,
        rating=1,
        comment='Trying to review another customer booking.',
    )

    assert response.status_code == 404


def test_reviews_must_match_a_listing_that_still_exists(review_site):
    booking_id = make_booking(review_site['guest_id'], f'missing-listing-{uuid.uuid4().hex[:8]}')

    response = post_review(
        review_site['guest'],
        booking_id=booking_id,
        rating=4,
        comment='The booked listing was removed before the review.',
    )

    assert response.status_code == 409


def test_stay_reviews_use_the_accommodation_listing(review_site):
    booking_id = make_booking(
        review_site['guest_id'],
        review_site['property_slug'],
        booking_type='property',
        property_id=review_site['property_id'],
        room_id=None,
        schedule_id=None,
        date=days_ago(10),
        time='',
        check_in=days_ago(5),
        check_out=days_ago(3),
        nights=2,
        amount=18000,
    )

    response = post_review(
        review_site['guest'],
        booking_id=booking_id,
        rating=4,
        comment='Quiet villa a short walk from the beach.',
    )

    assert response.status_code == 201
    review = response.get_json()['review']
    assert review['target_type'] == 'property'
    assert review['target_id'] == review_site['property_slug']
    assert review['place'] == 'Review Test Beach House'

    catalogue = review_site['guest']['client'].get('/api/catalogue').get_json()
    listing = next(
        item for item in catalogue['properties'] if item['slug'] == review_site['property_slug']
    )
    assert listing['rating'] == 4.0
    assert listing['review_count'] == 1


def test_stays_cannot_be_reviewed_before_check_out(review_site):
    booking_id = make_booking(
        review_site['guest_id'],
        review_site['property_slug'],
        booking_type='property',
        property_id=review_site['property_id'],
        room_id=None,
        schedule_id=None,
        date=days_ahead(2),
        time='',
        check_in=days_ahead(2),
        check_out=days_ahead(4),
        nights=2,
        amount=18000,
    )

    response = post_review(
        review_site['guest'],
        booking_id=booking_id,
        rating=5,
        comment='Reviewing a stay that has not ended yet.',
    )

    assert response.status_code == 409


def test_my_bookings_reminds_customers_to_review(review_site):
    reviewable = make_booking(review_site['guest_id'], review_site['tour_slug'])
    upcoming = make_booking(
        review_site['guest_id'],
        review_site['tour_slug'],
        date=days_ahead(6),
    )
    unpaid = make_booking(
        review_site['guest_id'],
        review_site['tour_slug'],
        payment_status='pending',
        status='requested',
    )

    response = review_site['guest']['client'].get('/api/customer/bookings')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['pending_reviews'] == 1
    states = {booking['id']: booking for booking in payload['bookings']}
    assert states[reviewable]['can_review'] is True
    assert states[reviewable]['review_status'] == 'ready'
    assert states[reviewable]['review'] is None
    assert states[upcoming]['can_review'] is False
    assert states[upcoming]['review_status'] == 'upcoming'
    assert states[unpaid]['can_review'] is False
    assert states[unpaid]['review_status'] == 'ineligible'

    post_review(
        review_site['guest'],
        booking_id=reviewable,
        rating=5,
        comment='Reviewed straight from my account.',
    )
    refreshed = review_site['guest']['client'].get('/api/customer/bookings').get_json()

    assert refreshed['pending_reviews'] == 0
    reviewed = next(booking for booking in refreshed['bookings'] if booking['id'] == reviewable)
    assert reviewed['can_review'] is False
    assert reviewed['review_status'] == 'reviewed'
    assert reviewed['review']['rating'] == 5
    assert reviewed['review']['comment'] == 'Reviewed straight from my account.'


def test_property_ratings_average_published_reviews(review_site):
    with application.app.app_context():
        application.db.session.add_all([
            application.Review(
                reviewer_name='First Guest',
                reviewer_email='first@example.test',
                place='Review Test Beach House',
                target_type='property',
                target_id=review_site['property_slug'],
                rating=5,
                comment='Perfect stay.',
            ),
            application.Review(
                reviewer_name='Second Guest',
                reviewer_email='second@example.test',
                place='Review Test Beach House',
                target_type='property',
                target_id=review_site['property_slug'],
                rating=3,
                comment='Good value.',
            ),
        ])
        application.db.session.commit()

    listing_reviews = review_site['guest']['client'].get(
        f"/reviews?target_type=property&target_id={review_site['property_slug']}"
    ).get_json()

    assert len(listing_reviews['reviews']) == 2
    assert listing_reviews['summary'] == {'rating': 4.0, 'review_count': 2}

    catalogue = review_site['guest']['client'].get('/api/catalogue').get_json()
    listing = next(
        item for item in catalogue['properties'] if item['slug'] == review_site['property_slug']
    )
    assert listing['rating'] == 4.0
    assert listing['review_count'] == 2


@pytest.mark.parametrize('overrides', [
    {'rating': 0},
    {'rating': 6},
    {'comment': ''},
    {'comment': 'x' * 3001},
])
def test_review_rating_and_comment_are_validated(review_site, overrides):
    booking_id = make_booking(review_site['guest_id'], review_site['tour_slug'])
    payload = {
        'booking_id': booking_id,
        'rating': 5,
        'comment': 'A valid review used to exercise validation.',
    }
    payload.update(overrides)

    response = post_review(review_site['guest'], **payload)

    assert response.status_code == 400
    assert 'error' in response.get_json()


def test_community_reviews_link_back_to_listings():
    tour_slug = f'community-tour-{uuid.uuid4().hex[:10]}'
    stay_slug = f'community-stay-{uuid.uuid4().hex[:10]}'
    with application.app.app_context():
        application.db.session.add_all([
            application.Tour(
                slug=tour_slug,
                name='Community Review Sail',
                description='A dhow sail used to test the community review feed.',
                duration='Two hours',
                price=3000,
                category='Dhow & Island Hopping',
                image_url='pictures/187168867.jpg',
            ),
            application.Property(
                slug=stay_slug,
                owner_name='Community Test Owner',
                owner_email='community-owner@example.test',
                name='Community Review Villa',
                property_type='villa',
                location='Shela',
                price_per_night=9500,
                guests=4,
                description='A villa used to test the community review feed.',
                image_url='pictures/187747945.jpg',
            ),
        ])
        application.db.session.commit()
        session = application.db.session
        session.add_all([
            application.Review(
                reviewer_name='Amina',
                reviewer_email='amina@example.test',
                place='Lamu',
                target_type='tour',
                target_id=tour_slug,
                rating=5,
                comment='A calm evening on the water with a guide who knew every channel.',
            ),
            application.Review(
                reviewer_name='Peter',
                reviewer_email='peter@example.test',
                place='Shela',
                target_type='property',
                target_id=stay_slug,
                rating=4,
                comment='Quiet, cool rooms and a short walk to the beach.',
            ),
        ])
        session.commit()

    client = application.app.test_client()
    data = client.get('/api/community/reviews?limit=60').get_json()

    tour_review = next(item for item in data['reviews'] if item['target_id'] == tour_slug)
    assert tour_review['listing_name'] == 'Community Review Sail'
    assert tour_review['url'] == f'/tour-details.html?id={tour_slug}'
    assert tour_review['listing_image'] == 'pictures/187168867.jpg'

    stay_review = next(item for item in data['reviews'] if item['target_id'] == stay_slug)
    assert stay_review['url'] == f'/booking.html?stay={stay_slug}'

    summary = data['summary']
    assert summary['review_count'] == sum(row['count'] for row in summary['distribution'])
    assert [row['rating'] for row in summary['distribution']] == [5, 4, 3, 2, 1]
    assert summary['tour_count'] >= 1 and summary['property_count'] >= 1

    tours_only = client.get('/api/community/reviews?target_type=tour&limit=60').get_json()
    assert tours_only['reviews']
    assert all(item['target_type'] == 'tour' for item in tours_only['reviews'])
    assert client.get('/api/community/reviews?target_type=hotel').status_code == 400

