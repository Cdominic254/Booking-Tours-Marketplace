"""Wishlist: signed-in customers save tours and stays, guests are told to sign in."""

import uuid

import pytest

import app as application

PASSWORD = 'wishlist-test-password'


@pytest.fixture
def wishlist_site():
    """Two customer accounts plus one tour and one accommodation to save."""
    tour_slug = f'wishlist-tour-{uuid.uuid4().hex[:10]}'
    property_slug = f'wishlist-stay-{uuid.uuid4().hex[:10]}'
    emails = [f'wishlist-{label}-{uuid.uuid4().hex}@example.test' for label in ('guest', 'stranger')]
    with application.app.app_context():
        users = [
            application.User(
                name='Wishlist Guest' if index == 0 else 'Wishlist Stranger',
                email=email,
                password_hash=application.generate_password_hash(PASSWORD),
            )
            for index, email in enumerate(emails)
        ]
        tour = application.Tour(
            slug=tour_slug,
            name='Wishlist Test Dhow Sail',
            description='A tour used to test saved listings.',
            duration='Three hours',
            price=3200,
            category='Dhow & Island Hopping',
        )
        listing = application.Property(
            slug=property_slug,
            owner_name='Wishlist Test Owner',
            owner_email='wishlist-owner@example.test',
            name='Wishlist Test Beach House',
            property_type='villa',
            location='Shela',
            price_per_night=11000,
            guests=4,
            description='An accommodation used to test saved listings.',
            image_url='pictures/187747945.jpg',
        )
        application.db.session.add_all([*users, tour, listing])
        application.db.session.commit()
        user_ids = [user.id for user in users]
        property_id = listing.id

    accounts = []
    for email in emails:
        client = application.app.test_client()
        response = client.post('/login', data={'email': email, 'password': PASSWORD})
        assert response.status_code == 302
        with client.session_transaction() as session:
            csrf_token = session['customer_csrf']
        accounts.append({'client': client, 'csrf': csrf_token, 'email': email})

    yield {
        'guest': accounts[0],
        'stranger': accounts[1],
        'user_ids': user_ids,
        'tour_slug': tour_slug,
        'property_slug': property_slug,
    }

    with application.app.app_context():
        application.SavedItem.query.filter(
            application.SavedItem.user_id.in_(user_ids)
        ).delete(synchronize_session=False)
        tour = application.db.session.get(application.Tour, tour_slug)
        if tour:
            application.db.session.delete(tour)
        listing = application.Property.query.filter_by(slug=property_slug).first()
        if listing:
            application.db.session.delete(listing)
        for user_id in user_ids:
            user = application.db.session.get(application.User, user_id)
            if user:
                application.db.session.delete(user)
        application.db.session.commit()


def save(account, listing_type, listing_slug, csrf_token=True):
    headers = {'Accept': 'application/json'}
    if csrf_token:
        headers['X-CSRF-Token'] = account['csrf']
    return account['client'].post(
        '/api/customer/saved',
        json={'listing_type': listing_type, 'listing_slug': listing_slug},
        headers=headers,
    )


def test_guests_are_told_to_sign_in():
    anonymous = application.app.test_client()

    listed = anonymous.get('/api/customer/saved')
    assert listed.status_code == 401
    assert 'Sign in' in listed.get_json()['error']

    blocked = anonymous.post(
        '/api/customer/saved',
        json={'listing_type': 'tour', 'listing_slug': 'any-tour'},
        headers={'Accept': 'application/json'},
    )
    assert blocked.status_code == 401


def test_saving_a_tour_returns_the_live_card(wishlist_site):
    guest = wishlist_site['guest']
    response = save(guest, 'tour', wishlist_site['tour_slug'])

    assert response.status_code == 201
    payload = response.get_json()
    assert payload['already_saved'] is False
    item = payload['item']
    assert item['listing_type'] == 'tour'
    assert item['listing_slug'] == wishlist_site['tour_slug']
    assert item['name'] == 'Wishlist Test Dhow Sail'
    assert item['listing_type_label'] == 'Experience'
    assert item['price'] == 3200
    assert item['price_unit'] == 'per guest'
    assert item['still_listed'] is True
    assert item['url'] == f"/tour-details.html?id={wishlist_site['tour_slug']}"


def test_saving_the_same_listing_twice_is_not_an_error(wishlist_site):
    guest = wishlist_site['guest']

    first = save(guest, 'property', wishlist_site['property_slug'])
    assert first.status_code == 201
    second = save(guest, 'property', wishlist_site['property_slug'])

    assert second.status_code == 200
    assert second.get_json()['already_saved'] is True
    assert guest['client'].get('/api/customer/saved').get_json()['count'] == 1


def test_saving_requires_a_csrf_token(wishlist_site):
    response = save(wishlist_site['guest'], 'tour', wishlist_site['tour_slug'], csrf_token=False)

    assert response.status_code == 403


def test_only_tours_and_stays_can_be_saved(wishlist_site):
    guest = wishlist_site['guest']

    bad_type = save(guest, 'service', 'airport-transfer')
    assert bad_type.status_code == 400

    unknown = save(guest, 'tour', 'no-such-tour-slug')
    assert unknown.status_code == 404

    missing_slug = guest['client'].post(
        '/api/customer/saved',
        json={'listing_type': 'tour', 'listing_slug': ''},
        headers={'Accept': 'application/json', 'X-CSRF-Token': guest['csrf']},
    )
    assert missing_slug.status_code == 400


def test_the_wishlist_lists_newest_first_with_a_csrf_token(wishlist_site):
    guest = wishlist_site['guest']
    save(guest, 'tour', wishlist_site['tour_slug'])
    save(guest, 'property', wishlist_site['property_slug'])

    response = guest['client'].get('/api/customer/saved')
    assert response.status_code == 200
    payload = response.get_json()

    assert payload['count'] == 2
    assert payload['limit'] == application.WISHLIST_LIMIT
    assert payload['csrf_token'] == guest['csrf']
    assert [item['listing_type'] for item in payload['items']] == ['property', 'tour']
    stay = payload['items'][0]
    assert stay['name'] == 'Wishlist Test Beach House'
    assert stay['listing_type_label'] == 'Place to stay'
    assert stay['price_unit'] == 'per night'
    assert stay['url'].startswith('/booking.html?stay=wishlist-stay-')
    assert stay['destination_name'] == 'Lamu'


def test_removing_and_clearing_saved_listings(wishlist_site):
    guest = wishlist_site['guest']
    tour_item = save(guest, 'tour', wishlist_site['tour_slug']).get_json()['item']
    property_item = save(guest, 'property', wishlist_site['property_slug']).get_json()['item']

    removed = guest['client'].delete(
        f"/api/customer/saved/{tour_item['id']}",
        headers={'Accept': 'application/json', 'X-CSRF-Token': guest['csrf']},
    )
    assert removed.status_code == 200
    assert removed.get_json()['removed'] == tour_item['id']
    assert guest['client'].get('/api/customer/saved').get_json()['count'] == 1

    cleared = guest['client'].delete(
        '/api/customer/saved',
        headers={'Accept': 'application/json', 'X-CSRF-Token': guest['csrf']},
    )
    assert cleared.status_code == 200
    assert cleared.get_json()['removed'] == 1
    assert guest['client'].get('/api/customer/saved').get_json()['items'] == []

    blocked = guest['client'].delete(
        f"/api/customer/saved/{property_item['id']}",
        headers={'Accept': 'application/json'},
    )
    assert blocked.status_code == 403


def test_customers_cannot_touch_another_wishlist(wishlist_site):
    guest_item = save(wishlist_site['guest'], 'tour', wishlist_site['tour_slug']).get_json()['item']

    stranger = wishlist_site['stranger']
    assert stranger['client'].get('/api/customer/saved').get_json()['count'] == 0

    response = stranger['client'].delete(
        f"/api/customer/saved/{guest_item['id']}",
        headers={'Accept': 'application/json', 'X-CSRF-Token': stranger['csrf']},
    )
    assert response.status_code == 404
    assert wishlist_site['guest']['client'].get('/api/customer/saved').get_json()['count'] == 1


def test_deleted_listings_stay_on_the_wishlist_until_removed(wishlist_site):
    guest = wishlist_site['guest']
    save(guest, 'tour', wishlist_site['tour_slug'])

    with application.app.app_context():
        application.db.session.delete(application.db.session.get(application.Tour, wishlist_site['tour_slug']))
        application.db.session.commit()

    payload = guest['client'].get('/api/customer/saved').get_json()
    assert payload['count'] == 1
    item = payload['items'][0]
    assert item['still_listed'] is False
    assert item['name'] == wishlist_site['tour_slug'].replace('-', ' ').title()
    assert item['url'] == ''

    removed = guest['client'].delete(
        f"/api/customer/saved/{item['id']}",
        headers={'Accept': 'application/json', 'X-CSRF-Token': guest['csrf']},
    )
    assert removed.status_code == 200

    with application.app.app_context():
        application.db.session.add(application.Tour(
            slug=wishlist_site['tour_slug'],
            name='Wishlist Test Dhow Sail',
            description='Restored so fixture cleanup can delete it again.',
            duration='Three hours',
            price=3200,
            category='Dhow & Island Hopping',
        ))
        application.db.session.commit()


def test_the_wishlist_has_a_limit(wishlist_site, monkeypatch):
    guest = wishlist_site['guest']
    monkeypatch.setattr(application, 'WISHLIST_LIMIT', 1)

    assert save(guest, 'tour', wishlist_site['tour_slug']).status_code == 201
    full = save(guest, 'property', wishlist_site['property_slug'])

    assert full.status_code == 409
    assert 'full' in full.get_json()['error']

    # Saving something already on the wishlist still reports it instead of the limit.
    again = save(guest, 'tour', wishlist_site['tour_slug'])
    assert again.status_code == 200


def test_sign_in_can_return_to_the_wishlist(wishlist_site):
    email = wishlist_site['guest']['email']
    client = application.app.test_client()

    response = client.post('/login', data={'email': email, 'password': PASSWORD, 'next': '/wishlist.html'})
    assert response.status_code == 302
    assert response.headers['Location'] == '/wishlist.html'

    unsafe = application.app.test_client()
    response = unsafe.post(
        '/login',
        data={'email': email, 'password': PASSWORD, 'next': 'https://example.test/steal'},
    )
    assert response.status_code == 302
    assert response.headers['Location'] == '/booking.html'


def test_the_wishlist_page_is_served(wishlist_site):
    response = wishlist_site['guest']['client'].get('/wishlist.html')

    assert response.status_code == 200
    assert b'<div id="root">' in response.data
