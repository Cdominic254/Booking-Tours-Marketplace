import uuid

import pytest

import app as application


def unique_token(prefix='op'):
    return f'{prefix}{uuid.uuid4().hex[:8]}'


def service_payload(name, **overrides):
    payload = {
        'name': name,
        'service_type': 'transfer',
        'description': 'Airport pickup to the old town with a private driver and air conditioning.',
        'price_from': 2500,
        'price_unit': 'per trip',
        'location': 'Manda Airport, Lamu',
        'destination': 'lamu',
        'coverage': ['Manda Airport', 'Lamu old town'],
        'inclusions': ['Meet and greet', 'Bottled water'],
    }
    payload.update(overrides)
    return payload


def remove_vendors(vendor_ids):
    with application.app.app_context():
        for vendor_id in vendor_ids:
            for service in application.Service.query.filter_by(vendor_id=vendor_id).all():
                application.db.session.delete(service)
            for tour in application.Tour.query.filter_by(vendor_id=vendor_id).all():
                application.TourSchedule.query.filter_by(tour_slug=tour.slug).delete()
                application.db.session.delete(tour)
            for listing in application.Property.query.filter_by(vendor_id=vendor_id).all():
                application.db.session.delete(listing)
            vendor = application.db.session.get(application.VendorAccount, vendor_id)
            if vendor:
                application.db.session.delete(vendor)
        application.db.session.commit()


@pytest.fixture
def admin_client():
    email = f'operator-admin-{uuid.uuid4().hex}@example.test'
    with application.app.app_context():
        admin = application.AdminAccount(
            name='Operator admin',
            email=email,
            password_hash=application.generate_password_hash('operator-admin-password'),
        )
        application.db.session.add(admin)
        application.db.session.commit()
        admin_id = admin.id

    client = application.app.test_client()
    assert client.post('/admin/login', data={
        'email': email,
        'password': 'operator-admin-password',
    }).status_code == 302
    with client.session_transaction() as session:
        csrf_token = session['admin_csrf']
    yield client, {'X-CSRF-Token': csrf_token}

    with application.app.app_context():
        application.AdminAccount.query.filter_by(id=admin_id).delete()
        application.db.session.commit()


@pytest.fixture
def operator_team():
    """Two signed-in suppliers: a safari operator and a transport company."""
    records = []
    with application.app.app_context():
        for label, business_types in (('safari', 'safari,tours'), ('transport', 'transport')):
            vendor = application.VendorAccount(
                name=f'Operator {label.title()} {unique_token("v")}',
                email=f'operator-{label}-{uuid.uuid4().hex}@example.test',
                password_hash=application.generate_password_hash('operator-password'),
                slug=f'operator-{label}-{uuid.uuid4().hex[:10]}',
                business_types=business_types,
                location='Lamu',
                phone='+254712000111',
                description=f'{label.title()} supplier used by the operator service tests.',
            )
            application.db.session.add(vendor)
            records.append(vendor)
        application.db.session.commit()
        accounts = [(vendor.email, vendor.id) for vendor in records]

    clients = []
    for email, vendor_id in accounts:
        client = application.app.test_client()
        assert client.post(
            '/vendor/login',
            data={'email': email, 'password': 'operator-password'},
        ).status_code == 302
        with client.session_transaction() as session:
            csrf_token = session['vendor_csrf']
        clients.append((client, {'X-CSRF-Token': csrf_token}, vendor_id))

    yield clients

    remove_vendors([vendor_id for _, _, vendor_id in clients])


def test_vendor_registration_captures_the_operator_profile():
    client = application.app.test_client()
    token = client.get('/api/vendor/registration-token').get_json()['csrf_token']
    payload = {
        'name': f'Bahari Safaris {unique_token("r")}',
        'email': f'bahari-{uuid.uuid4().hex}@example.test',
        'password': 'bahari-password-123',
        'business_types': ['safari', 'transport'],
        'location': 'Lamu',
        'phone': '+254712345678',
        'website': 'https://bahari.example.test',
        'description': 'Multi-day safaris and airport transfers run from Lamu.',
    }
    response = client.post('/vendor/register', json=payload, headers={'X-CSRF-Token': token})
    assert response.status_code == 201
    registered = response.get_json()
    vendor = registered['vendor']

    assert vendor['business_types'] == ['safari', 'transport']
    assert vendor['business_type_labels'] == ['Safari operator', 'Transport & transfers']
    assert vendor['slug']
    with application.app.app_context():
        stored = application.db.session.get(application.VendorAccount, vendor['id'])
        assert stored.email == payload['email']
        assert stored.password_hash != payload['password']
        assert stored.slug == vendor['slug']

    profile = client.get('/api/vendor/profile').get_json()['vendor']
    assert profile['slug'] == vendor['slug']
    assert profile['location'] == 'Lamu'

    updated = client.put('/api/vendor/profile', json={
        'name': vendor['name'],
        'business_types': ['safari'],
        'location': 'Shela',
        'phone': '+254712345678',
        'website': '',
        'description': 'Multi-day safaris from Shela.',
    }, headers={'X-CSRF-Token': registered['csrf_token']})
    assert updated.status_code == 200
    assert updated.get_json()['vendor']['business_types'] == ['safari']
    assert updated.get_json()['vendor']['location'] == 'Shela'

    remove_vendors([vendor['id']])


def test_vendor_registration_defaults_to_tour_operator_and_rejects_unknown_business_types():
    client = application.app.test_client()

    token = client.get('/api/vendor/registration-token').get_json()['csrf_token']
    rejected = client.post('/vendor/register', json={
        'name': f'Unknown Trade {unique_token("r")}',
        'email': f'unknown-{uuid.uuid4().hex}@example.test',
        'password': 'unknown-password-123',
        'business_types': ['space-travel'],
    }, headers={'X-CSRF-Token': token})
    assert rejected.status_code == 400
    assert 'business type' in rejected.get_json()['error']

    token = client.get('/api/vendor/registration-token').get_json()['csrf_token']
    accepted = client.post('/vendor/register', json={
        'name': f'Default Operator {unique_token("r")}',
        'email': f'default-{uuid.uuid4().hex}@example.test',
        'password': 'default-password-123',
    }, headers={'X-CSRF-Token': token})
    assert accepted.status_code == 201
    vendor = accepted.get_json()['vendor']
    assert vendor['business_types'] == ['tours']
    assert vendor['business_type_labels'] == ['Tour operator']

    remove_vendors([vendor['id']])


def test_safari_tour_details_are_published_with_operator_labels(operator_team):
    client, headers, vendor_id = operator_team[0]
    with application.app.app_context():
        destination = application.Destination.query.first().slug

    response = client.post('/api/vendor/tours', json={
        'name': f'{unique_token("safari")} Mara Migration Safari',
        'description': 'Five days tracking the migration with a private guide and camp stays.',
        'duration': '5 days',
        'price': 96000,
        'category': 'Safari',
        'destination': destination,
        'tour_type': 'multi-day-safari',
        'group_type': 'shared',
        'languages': 'English, Swahili',
        'itinerary': ['Day 1 | Transfer and afternoon game drive'],
        'inclusions': 'Park fees',
    }, headers=headers)
    assert response.status_code == 201
    tour = response.get_json()['tour']
    assert tour['tour_type_label'] == 'Multi-day safari'
    assert tour['group_type_label'] == 'Shared group'
    assert tour['duration_days'] == 5
    assert tour['languages'] == ['English', 'Swahili']

    rejected = client.post('/api/vendor/tours', json={
        'name': f'{unique_token("safari")} Invalid Safari',
        'description': 'A tour with an unknown style.',
        'duration': '2 days',
        'price': 30000,
        'tour_type': 'balloon-safari',
    }, headers=headers)
    assert rejected.status_code == 400

    catalogue = client.get('/api/vendor/catalogue').get_json()
    assert ['multi-day-safari', 'Multi-day safari'] in catalogue['tour_types']
    assert ['shared', 'Shared group'] in catalogue['tour_group_types']
    assert catalogue['vendor']['id'] == vendor_id


def test_vendor_service_crud_is_limited_to_the_owner(operator_team):
    first_client, first_headers, first_id = operator_team[0]
    second_client, second_headers, _ = operator_team[1]
    name = f'{unique_token("svc")} Reef Transfer'

    created = first_client.post('/api/vendor/services', json=service_payload(name), headers=first_headers)
    assert created.status_code == 201
    service = created.get_json()['service']
    assert service['service_type_label'] == 'Airport & hotel transfer'
    assert service['price_unit'] == 'per trip'
    assert service['coverage'] == ['Manda Airport', 'Lamu old town']

    assert [item['slug'] for item in first_client.get('/api/vendor/catalogue').get_json()['services']] == [service['slug']]
    assert second_client.get('/api/vendor/catalogue').get_json()['services'] == []
    assert second_client.put(
        f"/api/vendor/services/{service['slug']}",
        json=service_payload(name),
        headers=second_headers,
    ).status_code == 404
    assert second_client.delete(f"/api/vendor/services/{service['slug']}", headers=second_headers).status_code == 404

    updated = first_client.put(f"/api/vendor/services/{service['slug']}", json=service_payload(
        name, price_from=3200, price_unit='per group', service_type='guide',
    ), headers=first_headers)
    assert updated.status_code == 200
    assert updated.get_json()['service']['price_from'] == 3200
    assert updated.get_json()['service']['service_type'] == 'guide'

    assert first_client.delete(f"/api/vendor/services/{service['slug']}", headers=first_headers).status_code == 204
    assert first_client.get('/api/vendor/catalogue').get_json()['services'] == []
    assert first_id


def test_catalogue_operator_profile_and_search_publish_active_services(operator_team):
    client, headers, _ = operator_team[0]
    token = unique_token('reef')
    name = f'{token} Reef Transfer'
    created = client.post('/api/vendor/services', json=service_payload(name), headers=headers)
    assert created.status_code == 201
    service = created.get_json()['service']
    with application.app.app_context():
        vendor = application.db.session.get(application.VendorAccount, service['vendor_id'])
        vendor_slug = vendor.slug
        vendor_name = vendor.name
    assert vendor_slug

    catalogue = client.get('/api/catalogue').get_json()
    published = next(item for item in catalogue['services'] if item['slug'] == service['slug'])
    assert published['operator']['name'] == vendor_name
    assert 'email' not in published['operator']
    assert any(operator['slug'] == vendor_slug for operator in catalogue['operators'])

    profile = client.get(f'/api/operators/{vendor_slug}')
    assert profile.status_code == 200
    profile_data = profile.get_json()
    assert profile_data['operator']['name'] == vendor_name
    assert 'email' not in profile_data['operator']
    assert [item['slug'] for item in profile_data['services']] == [service['slug']]
    assert profile_data['tours'] == []
    assert profile_data['properties'] == []

    search = client.get(f'/api/search?q={token}&type=service').get_json()
    assert search['counts']['service'] >= 1
    match = next(result for result in search['results'] if result['slug'] == service['slug'])
    assert match['url'] == f'/operators/{vendor_slug}#service-{service["slug"]}'
    assert match['type_label'] == 'Service'

    hidden = client.put(f"/api/vendor/services/{service['slug']}", json=service_payload(name, is_active='false'), headers=headers)
    assert hidden.status_code == 200
    assert hidden.get_json()['service']['is_active'] is False
    assert all(item['slug'] != service['slug'] for item in client.get('/api/catalogue').get_json()['services'])
    assert client.get(f'/api/search?q={token}&type=service').get_json()['counts']['service'] == 0
    assert client.get(f'/api/operators/{vendor_slug}').get_json()['services'] == []


def test_admin_can_publish_services_for_a_supplier(admin_client, operator_team):
    admin, admin_headers = admin_client
    _, _, vendor_id = operator_team[1]
    name = f'{unique_token("adm")} Dhow Photography'

    created = admin.post('/api/admin/services', json=service_payload(
        name, vendor_id=vendor_id, service_type='photography', price_unit='per day',
    ), headers=admin_headers)
    assert created.status_code == 201
    service = created.get_json()['service']
    assert service['vendor_id'] == vendor_id

    catalogue = admin.get('/api/admin/catalogue').get_json()
    entry = next(item for item in catalogue['services'] if item['slug'] == service['slug'])
    assert entry['vendor_name']
    assert ['photography', 'Photography'] in catalogue['service_types']

    assert admin.delete(f"/api/admin/services/{service['slug']}", headers=admin_headers).status_code == 204
    assert all(
        item['slug'] != service['slug']
        for item in admin.get('/api/admin/catalogue').get_json()['services']
    )
    assert all(item['slug'] != service['slug'] for item in application.app.test_client().get('/api/catalogue').get_json()['services'])


def test_public_pages_serve_the_react_app_for_services_and_operator_profiles(tmp_path, monkeypatch):
    dist = tmp_path / 'dist'
    assets = dist / 'assets'
    assets.mkdir(parents=True)
    (dist / 'index.html').write_text('<div id="root">React app</div>', encoding='utf-8')
    (assets / 'main.js').write_text('console.log("React");', encoding='utf-8')
    monkeypatch.setattr(application, 'FRONTEND_DIST', str(dist))

    client = application.app.test_client()
    assert b'React app' in client.get('/services.html').data
    assert b'React app' in client.get('/operators/lamu-safaris').data
