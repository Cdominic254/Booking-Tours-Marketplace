import uuid

import pytest

import app as application


@pytest.fixture
def client():
    return application.app.test_client()


@pytest.fixture
def searchable_catalogue():
    token = f'zz{uuid.uuid4().hex[:8]}'
    noise = f'qq{uuid.uuid4().hex[:8]}'
    with application.app.app_context():
        destination = application.Destination(
            slug=f'search-place-{token}',
            name=f'Shela Cove {token}',
            description='Quiet sandbank with a coral lagoon.',
            image_url=None,
            search_location='Shela',
        )
        title_match = application.Tour(
            slug=f'search-tour-title-{token}',
            name=f'{token} Sunset Cruise',
            description='A slow sail past the reef.',
            duration='2 hours',
            price=4200,
            category='Sailing',
            itinerary='Sail out at sunset.',
            inclusions='Water',
            destination=destination.slug,
        )
        body_match = application.Tour(
            slug=f'search-tour-body-{token}',
            name=f'Harbour Walk {noise}',
            description=f'An evening walk that passes the {token} landing stage.',
            duration='90 minutes',
            price=2500,
            category='Heritage',
            itinerary='Meet at the jetty.',
            inclusions='Guide',
            destination=destination.slug,
        )
        listing = application.Property(
            slug=f'search-accommodation-{token}',
            owner_name='Search Test',
            owner_email='search@example.test',
            name=f'Lagoon Rental {noise}',
            property_type='rental',
            location='Shela',
            destination=destination.slug,
            amenities='Pool\nSea view',
            price_per_night=9500,
            guests=4,
            description=f'A calm rental beside the lagoon, a short walk from {token}.',
        )
        application.db.session.add_all([destination, title_match, body_match, listing])
        application.db.session.commit()
        slugs = {
            'destination': destination.slug,
            'tour_title': title_match.slug,
            'tour_body': body_match.slug,
            'accommodation': listing.slug,
        }

    yield token, slugs

    with application.app.app_context():
        application.TourSchedule.query.filter(
            application.TourSchedule.tour_slug.in_([slugs['tour_title'], slugs['tour_body']])
        ).delete(synchronize_session=False)
        application.Tour.query.filter(
            application.Tour.slug.in_([slugs['tour_title'], slugs['tour_body']])
        ).delete(synchronize_session=False)
        application.Property.query.filter_by(slug=slugs['accommodation']).delete()
        application.Destination.query.filter_by(slug=slugs['destination']).delete()
        application.db.session.commit()


def test_search_requires_a_query(client):
    response = client.get('/api/search')

    assert response.status_code == 400
    assert 'error' in response.get_json()


@pytest.mark.parametrize('query', ['', '   ', 'a'])
def test_search_rejects_unusable_terms(client, query):
    assert client.get('/api/search', query_string={'q': query}).status_code == 400


def test_search_finds_every_listing_type(client, searchable_catalogue):
    token, slugs = searchable_catalogue

    payload = client.get('/api/search', query_string={'q': token}).get_json()

    assert payload['terms'] == [token]
    assert payload['query'] == token
    assert payload['type'] == 'all'
    found = {(result['type'], result['slug']) for result in payload['results']}
    assert ('tour', slugs['tour_title']) in found
    assert ('tour', slugs['tour_body']) in found
    assert ('accommodation', slugs['accommodation']) in found
    assert ('destination', slugs['destination']) in found
    assert payload['counts']['tour'] >= 2
    assert payload['counts']['accommodation'] >= 1
    assert payload['counts']['destination'] >= 1
    assert payload['total'] == len(payload['results'])


def test_search_ranks_title_matches_above_body_matches(client, searchable_catalogue):
    token, slugs = searchable_catalogue

    results = client.get('/api/search', query_string={'q': token}).get_json()['results']
    positions = {result['slug']: index for index, result in enumerate(results)}

    assert positions[slugs['tour_title']] < positions[slugs['tour_body']]
    assert results[0]['score'] >= results[-1]['score']


def test_search_filters_results_by_type(client, searchable_catalogue):
    token, slugs = searchable_catalogue

    payload = client.get('/api/search', query_string={'q': token, 'type': 'accommodation'}).get_json()

    assert payload['type'] == 'accommodation'
    assert payload['results']
    assert {result['type'] for result in payload['results']} == {'accommodation'}
    assert payload['total'] == 1
    assert payload['counts']['tour'] >= 2


def test_search_rejects_unknown_type(client, searchable_catalogue):
    token, _ = searchable_catalogue

    assert client.get('/api/search', query_string={'q': token, 'type': 'rooms'}).status_code == 400


def test_search_limits_result_count(client, searchable_catalogue):
    token, _ = searchable_catalogue

    payload = client.get('/api/search', query_string={'q': token, 'limit': 2}).get_json()

    assert len(payload['results']) == 2
    assert payload['total'] > 2


@pytest.mark.parametrize('limit', ['0', 'many', '999'])
def test_search_handles_awkward_limits(client, searchable_catalogue, limit):
    token, _ = searchable_catalogue

    response = client.get('/api/search', query_string={'q': token, 'limit': limit})

    if limit == 'many':
        assert response.status_code == 400
    else:
        assert response.status_code == 200
        assert 1 <= len(response.get_json()['results']) <= application.SEARCH_MAX_LIMIT


def test_search_ignores_punctuation_and_case(client, searchable_catalogue):
    token, slugs = searchable_catalogue

    payload = client.get('/api/search', query_string={'q': f'  {token.upper()}%  '}).get_json()

    assert payload['terms'] == [token]
    assert slugs['tour_title'] in {result['slug'] for result in payload['results']}


def test_search_truncates_long_queries(client):
    response = client.get('/api/search', query_string={'q': 'x' * 400})

    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload['query']) == application.SEARCH_MAX_QUERY_LENGTH
    assert payload['results'] == []


def test_search_snippet_mentions_the_matched_term(client, searchable_catalogue):
    token, slugs = searchable_catalogue

    results = client.get('/api/search', query_string={'q': token}).get_json()['results']
    accommodation = next(result for result in results if result['slug'] == slugs['accommodation'])

    assert token in accommodation['snippet'].lower()


def test_search_results_link_to_listing_pages(client, searchable_catalogue):
    token, slugs = searchable_catalogue

    results = client.get('/api/search', query_string={'q': token}).get_json()['results']
    by_slug = {result['slug']: result for result in results}

    assert by_slug[slugs['tour_title']]['url'].startswith('/tour-details.html?id=')
    assert by_slug[slugs['accommodation']]['url'].startswith('/booking.html?stay=')
    assert by_slug[slugs['destination']]['url'].startswith('/tours.html?destination=')
