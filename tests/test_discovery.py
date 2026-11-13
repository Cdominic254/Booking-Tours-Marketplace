import uuid
from datetime import datetime

import pytest

import app as application


@pytest.fixture
def client():
    return application.app.test_client()


@pytest.fixture
def admin_client():
    email = f'discovery-admin-{uuid.uuid4().hex}@example.test'
    with application.app.app_context():
        admin = application.AdminAccount(
            name='Discovery test admin',
            email=email,
            password_hash=application.generate_password_hash('discovery-admin-password'),
        )
        application.db.session.add(admin)
        application.db.session.commit()
        admin_id = admin.id

    client = application.app.test_client()
    response = client.post('/admin/login', data={'email': email, 'password': 'discovery-admin-password'})
    assert response.status_code == 302
    yield client

    with application.app.app_context():
        application.AdminAccount.query.filter_by(id=admin_id).delete()
        application.db.session.commit()


@pytest.fixture
def discovery_scene():
    """Three tours in one destination plus a stay, booked and reviewed."""
    token = f'dx{uuid.uuid4().hex[:8]}'
    destination_slug = f'discovery-place-{token}'
    slugs = {
        'value': f'{token}-value-tour',
        'mid': f'{token}-mid-tour',
        'premium': f'{token}-premium-tour',
        'stay': f'{token}-lagoon-stay',
        'destination': destination_slug,
    }

    with application.app.app_context():
        destination = application.Destination(
            slug=destination_slug,
            name=f'Discovery Cove {token}',
            description='A quiet test bay used to exercise discovery ranking.',
            image_url=None,
            search_location='Discovery',
        )
        value_tour = application.Tour(
            slug=slugs['value'],
            name=f'{token} Value Sail',
            description='The most affordable sailing departure in the bay.',
            duration='2 hours',
            price=1000,
            category='Sailing',
            destination=destination_slug,
        )
        mid_tour = application.Tour(
            slug=slugs['mid'],
            name=f'{token} Mid Sail',
            description='A mid-priced sailing departure that guests keep booking.',
            duration='3 hours',
            price=3000,
            category='Sailing',
            destination=destination_slug,
        )
        premium_tour = application.Tour(
            slug=slugs['premium'],
            name=f'{token} Premium Sail',
            description='A premium heritage departure with the same starting price.',
            duration='4 hours',
            price=3000,
            category='Heritage',
            destination=destination_slug,
        )
        stay = application.Property(
            slug=slugs['stay'],
            owner_name='Discovery Test',
            owner_email='discovery@example.test',
            name=f'{token} Lagoon Stay',
            property_type='rental',
            location='Discovery',
            destination=destination_slug,
            price_per_night=6000,
            guests=4,
            description='A test stay where the cheapest room sets the starting price.',
        )
        application.db.session.add_all([destination, value_tour, mid_tour, premium_tour, stay])
        application.db.session.flush()
        # Reclaimed primary keys can inherit rooms left behind by other fixtures.
        application.PropertyRoom.query.filter_by(property_id=stay.id).delete(synchronize_session=False)
        application.db.session.add_all([
            application.PropertyRoom(
                property_id=stay.id, name='Garden Room', guests=2, base_rate=4000, total_units=1,
            ),
            application.PropertyRoom(
                property_id=stay.id, name='Ocean Suite', guests=4, base_rate=9000, total_units=1,
            ),
            application.Review(
                reviewer_name='Guest One',
                reviewer_email='guest-one@example.test',
                place='Discovery Cove',
                target_type='tour',
                target_id=slugs['mid'],
                rating=5,
                comment='A wonderful afternoon on the water.',
            ),
            application.Review(
                reviewer_name='Guest Two',
                reviewer_email='guest-two@example.test',
                place='Discovery Cove',
                target_type='tour',
                target_id=slugs['mid'],
                rating=5,
                comment='The crew knew every corner of the bay.',
            ),
        ])
        for _ in range(8):
            application.db.session.add(application.Booking(
                name='Discovery Customer',
                email='discovery-customer@example.test',
                phone='0700000000',
                tour=slugs['mid'],
                date='2026-01-01',
                time='09:00',
                guests=2,
                amount=3000,
                payment_status='paid',
                created_at=datetime.utcnow(),
            ))
        application.db.session.commit()

    yield {'token': token, 'slugs': slugs}

    with application.app.app_context():
        tour_slugs = [slugs['value'], slugs['mid'], slugs['premium']]
        application.Booking.query.filter(application.Booking.tour.in_(tour_slugs)).delete(synchronize_session=False)
        application.Review.query.filter(application.Review.target_id.in_(tour_slugs)).delete(synchronize_session=False)
        listing = application.Property.query.filter_by(slug=slugs['stay']).first()
        if listing is not None:
            application.PropertyRoom.query.filter_by(property_id=listing.id).delete()
            application.db.session.delete(listing)
        application.Tour.query.filter(application.Tour.slug.in_(tour_slugs)).delete(synchronize_session=False)
        application.Destination.query.filter_by(slug=destination_slug).delete()
        application.db.session.commit()


def search_results(client, token, **params):
    payload = client.get('/api/search', query_string={'q': token, 'type': 'tour', **params}).get_json()
    return payload


def test_median_price_handles_empty_and_even_samples():
    assert application.median_price([]) == 0.0
    assert application.median_price([0, None, 4000]) == 4000.0
    assert application.median_price([1000, 3000, 5000]) == 3000.0
    assert application.median_price([1000, 2000, 3000, 8000]) == 2500.0


def test_price_comparison_labels_market_position():
    peers = [1000, 3000, 3000]

    cheaper = application.price_comparison(1000, peers, 'Discovery')
    typical = application.price_comparison(3100, peers, 'Discovery')
    expensive = application.price_comparison(6000, peers, 'Discovery')

    assert cheaper['position'] == 'below'
    assert cheaper['difference_percent'] == -66.7
    assert cheaper['median'] == 3000
    assert cheaper['label'] == 'Discovery'
    assert typical['position'] == 'typical'
    assert expensive['position'] == 'above'
    assert expensive['difference_percent'] == 100.0


def test_price_comparison_marks_missing_prices_unknown():
    assert application.price_comparison(0, [1000, 2000])['position'] == 'unknown'
    assert application.price_comparison(1000, [])['position'] == 'unknown'
    assert application.price_comparison(None, [0, 0])['position'] == 'unknown'


def test_listing_badges_need_real_evidence():
    below = {'position': 'below'}
    typical = {'position': 'typical'}

    assert application.listing_badges(
        rating=5.0, review_count=2, paid_bookings=0, recent_bookings=0, comparison=typical,
    ) == ['Top rated']
    assert application.listing_badges(
        rating=5.0, review_count=1, paid_bookings=0, recent_bookings=0, comparison=typical,
    ) == []
    assert application.listing_badges(
        rating=0, review_count=0, paid_bookings=3, recent_bookings=0, comparison=typical,
    ) == ['Popular']
    assert application.listing_badges(
        rating=0, review_count=0, paid_bookings=0, recent_bookings=2, comparison=typical,
    ) == ['Popular']
    assert application.listing_badges(
        rating=0, review_count=0, paid_bookings=0, recent_bookings=0, comparison=below,
    ) == ['Best value']
    assert application.listing_badges(
        rating=3.4, review_count=4, paid_bookings=0, recent_bookings=0, comparison=below,
    ) == []


def test_catalogue_exposes_demand_price_and_ratings(client, discovery_scene):
    slugs = discovery_scene['slugs']

    payload = client.get('/api/catalogue').get_json()

    tour = next(item for item in payload['tours'] if item['slug'] == slugs['mid'])
    assert tour['rating'] == 5.0
    assert tour['review_count'] == 2
    assert tour['paid_bookings'] == 8
    assert tour['recent_bookings'] == 8
    assert tour['price_from'] == 3000
    assert tour['price_comparison']['position'] == 'typical'
    assert tour['badges'] == ['Top rated', 'Popular']

    stay = next(item for item in payload['properties'] if item['slug'] == slugs['stay'])
    assert stay['price_from'] == 4000
    assert stay['price_to'] == 9000
    assert stay['room_types'] == 2
    assert stay['rating'] == 0
    assert stay['review_count'] == 0
    assert 'price_comparison' in stay


def test_catalogue_flags_underpriced_listing_as_best_value(client, discovery_scene):
    slugs = discovery_scene['slugs']

    payload = client.get('/api/catalogue').get_json()

    value = next(item for item in payload['tours'] if item['slug'] == slugs['value'])
    assert value['price_comparison']['position'] == 'below'
    assert value['price_comparison']['median'] == 3000
    assert value['price_comparison']['label'].startswith('Discovery Cove')
    assert value['badges'] == ['Best value']

    premium = next(item for item in payload['tours'] if item['slug'] == slugs['premium'])
    assert premium['price_comparison']['position'] == 'typical'
    assert premium['badges'] == []


def test_search_exposes_signal_fields(client, discovery_scene):
    token, slugs = discovery_scene['token'], discovery_scene['slugs']

    payload = search_results(client, token)

    assert payload['sort'] == 'relevance'
    results = {result['slug']: result for result in payload['results']}
    assert set(slugs[key] for key in ('value', 'mid', 'premium')) <= set(results)
    top = results[slugs['mid']]
    assert top['rating'] == 5.0
    assert top['review_count'] == 2
    assert top['paid_bookings'] == 8
    assert top['badges'] == ['Top rated', 'Popular']
    assert top['signal_score'] > results[slugs['value']]['signal_score']
    assert top['score'] == round(top['relevance_score'] + top['signal_score'], 1)


def test_data_signals_break_relevance_ties(client, discovery_scene):
    token, slugs = discovery_scene['token'], discovery_scene['slugs']

    results = search_results(client, token)['results']
    order = [result['slug'] for result in results]
    relevance = {result['slug']: result['relevance_score'] for result in results}

    assert relevance[slugs['value']] == relevance[slugs['mid']] == relevance[slugs['premium']]
    assert order.index(slugs['mid']) < order.index(slugs['value'])
    assert order.index(slugs['mid']) < order.index(slugs['premium'])
    assert order.index(slugs['value']) < order.index(slugs['premium'])


@pytest.mark.parametrize('sort, expected', [
    ('price_low', ['value', 'mid', 'premium']),
    ('rating', ['mid', 'value', 'premium']),
    ('popular', ['mid', 'premium', 'value']),
])
def test_search_sort_orders_results_by_signal(client, discovery_scene, sort, expected):
    token, slugs = discovery_scene['token'], discovery_scene['slugs']

    payload = search_results(client, token, sort=sort)
    order = [result['slug'] for result in payload['results']]

    assert payload['sort'] == sort
    assert order[:3] == [slugs[key] for key in expected]


def test_search_sort_price_high_starts_with_most_expensive(client, discovery_scene):
    token, slugs = discovery_scene['token'], discovery_scene['slugs']

    results = search_results(client, token, sort='price_high')['results']
    order = [result['slug'] for result in results]
    prices = [result['price'] for result in results]

    assert prices == sorted(prices, reverse=True)
    assert order.index(slugs['value']) == 2


def test_search_sort_price_low_ignores_unpriced_destinations(client, discovery_scene):
    token = discovery_scene['token']

    results = client.get('/api/search', query_string={'q': token, 'sort': 'price_low'}).get_json()['results']

    priced = [result['price'] for result in results if result['price'] is not None]
    assert priced == sorted(priced)
    assert results[-1]['type'] == 'destination'


def test_search_rejects_unknown_sort(client, discovery_scene):
    token = discovery_scene['token']

    response = client.get('/api/search', query_string={'q': token, 'sort': 'cheapest'})

    assert response.status_code == 400
    assert 'error' in response.get_json()


def test_recommendations_trend_from_real_bookings(client, discovery_scene):
    slugs = discovery_scene['slugs']

    payload = client.get('/api/recommendations', query_string={
        'type': 'tour', 'destination': slugs['destination'], 'limit': 6,
    }).get_json()

    assert payload['basis'] == 'trending'
    assert payload['seed'] is None
    assert payload['recommendations'][0]['slug'] == slugs['mid']
    assert payload['recommendations'][0]['reason'] == 'Trending now'
    keys = [(item['recent_bookings'], item['paid_bookings']) for item in payload['recommendations']]
    assert keys == sorted(keys, reverse=True)
    first = payload['recommendations'][0]
    assert first['price_unit'] == 'per guest'
    assert first['url'].startswith('/tour-details.html?id=')
    assert first['type'] == 'tour'


def test_recommendations_explain_similar_listings(client, discovery_scene):
    slugs = discovery_scene['slugs']

    payload = client.get('/api/recommendations', query_string={
        'type': 'tour',
        'slug': slugs['mid'],
        'destination': slugs['destination'],
    }).get_json()

    assert payload['basis'] == 'similar'
    assert payload['seed'] == {'type': 'tour', 'slug': slugs['mid'], 'name': f"{discovery_scene['token']} Mid Sail"}
    recommended = payload['recommendations']
    assert [item['slug'] for item in recommended] == [slugs['value'], slugs['premium']]
    assert recommended[0]['reason'] == 'Same destination and style'
    assert recommended[1]['reason'] == 'Same destination'


def test_recommendations_honour_excludes_and_limits(client, discovery_scene):
    slugs = discovery_scene['slugs']

    payload = client.get('/api/recommendations', query_string={
        'type': 'tour',
        'slug': slugs['mid'],
        'exclude': f"{slugs['value']},{slugs['premium']}",
        'limit': 2,
    }).get_json()

    listed = [item['slug'] for item in payload['recommendations']]
    assert slugs['value'] not in listed
    assert slugs['premium'] not in listed
    assert len(listed) <= 2


def test_recommendations_filter_by_destination(client, discovery_scene):
    slugs = discovery_scene['slugs']

    payload = client.get('/api/recommendations', query_string={
        'destination': slugs['destination'],
        'limit': 6,
    }).get_json()

    assert payload['recommendations']
    assert {item['destination'] for item in payload['recommendations']} == {slugs['destination']}


def test_recommendations_include_stays_with_room_ranges(client, discovery_scene):
    payload = client.get(
        '/api/recommendations',
        query_string={'type': 'accommodation', 'destination': discovery_scene['slugs']['destination']},
    ).get_json()

    stay = payload['recommendations'][0]
    assert stay['type'] == 'accommodation'
    assert stay['price_from'] == 4000
    assert stay['price_to'] == 9000
    assert stay['room_types'] == 2
    assert stay['price_unit'] == 'per night'
    assert stay['url'].startswith('/booking.html?stay=')


@pytest.mark.parametrize('params', [
    {'type': 'rooms'},
    {'limit': 'many'},
])
def test_recommendations_reject_bad_parameters(client, params):
    response = client.get('/api/recommendations', query_string=params)

    assert response.status_code == 400
    assert 'error' in response.get_json()


def test_recommendations_clamp_limit(client, discovery_scene):
    payload = client.get('/api/recommendations', query_string={'type': 'tour', 'limit': 99}).get_json()

    assert 1 <= len(payload['recommendations']) <= application.RECOMMENDATION_MAX_LIMIT


def test_admin_operations_report_price_insights(admin_client, discovery_scene):
    slugs = discovery_scene['slugs']

    response = admin_client.get('/api/admin/operations')

    assert response.status_code == 200
    analytics = response.get_json()['analytics']
    insights = analytics['price_insights']
    assert insights['tours']['listings'] >= 3
    assert insights['tours']['priced_listings'] <= insights['tours']['listings']
    assert insights['tours']['below_market'] >= 1
    assert insights['tours']['median_price'] > 0
    assert insights['stays']['listings'] >= 1
    assert insights['stays']['median_price'] > 0

    row = next(item for item in insights['listings'] if item['slug'] == slugs['mid'])
    assert row['kind'] == 'tour'
    assert row['price_from'] == 3000
    assert row['price_unit'] == 'per guest'
    assert row['paid_bookings'] == 8
    assert row['paid_revenue'] == 24000

    value_row = next(
        (item for item in insights['listings'] if item['slug'] == slugs['value']), None,
    )
    if value_row is not None:
        assert value_row['position'] == 'below'
        assert value_row['difference_percent'] < 0

    for row in insights['listings']:
        assert row['kind'] in {'tour', 'stay'}
        assert row['price_unit'] in {'per guest', 'per night'}
        assert {'price_from', 'price_to', 'median', 'position', 'paid_revenue'} <= set(row)
