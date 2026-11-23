import io
from uuid import uuid4

import pytest

import app as application


@pytest.fixture
def application_client():
    return application.app.test_client()


def test_login_attempts_are_rate_limited_by_ip_and_account(application_client):
    responses = [
        application_client.post(
            '/login',
            data={'email': 'guessed-user@example.test', 'password': 'incorrect'},
            environ_overrides={'REMOTE_ADDR': '203.0.113.41'},
        )
        for _ in range(6)
    ]

    assert [response.status_code for response in responses[:5]] == [302] * 5
    assert responses[5].status_code == 429


@pytest.mark.parametrize('login_path', ['/login', '/admin/login', '/vendor/login'])
def test_login_attempts_are_rate_limited_per_account_across_ips(application_client, login_path):
    responses = [
        application_client.post(
            login_path,
            data={'email': 'target-account@example.test', 'password': 'incorrect'},
            environ_overrides={'REMOTE_ADDR': f'203.0.113.{index + 1}'},
        )
        for index in range(11)
    ]

    assert [response.status_code for response in responses[:10]] == [302] * 10
    assert responses[10].status_code == 429


def test_successful_logins_do_not_consume_account_failure_limit(application_client):
    email = f'{uuid4().hex}@example.test'
    password = 'correct-password-for-test'
    with application.app.app_context():
        user = application.User(
            name='Rate Limit Test',
            email=email,
            password_hash=application.generate_password_hash(password),
        )
        application.db.session.add(user)
        application.db.session.commit()
        user_id = user.id

    try:
        responses = [
            application_client.post(
                '/login',
                data={'email': email, 'password': password},
                environ_overrides={'REMOTE_ADDR': f'203.0.113.{index + 1}'},
            )
            for index in range(11)
        ]

        assert [response.status_code for response in responses] == [302] * 11
        assert all(response.headers['Location'] == '/booking.html' for response in responses)
    finally:
        with application.app.app_context():
            user = application.db.session.get(application.User, user_id)
            if user:
                application.db.session.delete(user)
                application.db.session.commit()


def test_security_headers_are_added(application_client, monkeypatch):
    monkeypatch.setitem(application.app.config, 'SESSION_COOKIE_SECURE', True)

    response = application_client.get('/healthz')

    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert response.headers['X-Frame-Options'] == 'DENY'
    assert response.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'
    assert response.headers['Permissions-Policy'] == 'camera=(), geolocation=(), microphone=()'
    assert response.headers['Strict-Transport-Security'] == 'max-age=31536000'


def test_public_catalogue_exposes_configured_whatsapp_business_phone(application_client, monkeypatch):
    monkeypatch.setattr(application, 'WHATSAPP_BUSINESS_PHONE', '254712345678')

    response = application_client.get('/api/catalogue')

    assert response.status_code == 200
    assert response.get_json()['whatsapp_business_phone'] == '254712345678'


def test_review_submissions_are_rate_limited_for_anonymous_visitors(application_client):
    payload = {
        'booking_id': 1,
        'rating': 5,
        'comment': 'A review used to exercise the review rate limit.',
    }
    responses = [
        application_client.post(
            '/review-submit',
            json=payload,
            environ_overrides={'REMOTE_ADDR': '203.0.113.42'},
        )
        for _ in range(6)
    ]

    assert [response.status_code for response in responses[:5]] == [401] * 5
    assert responses[5].status_code == 429


def test_booking_checkout_creation_is_rate_limited(application_client, monkeypatch):
    monkeypatch.setattr(application, 'is_paystack_configured', lambda: False)
    responses = [
        application_client.post(
            '/booking-confirmation',
            json={},
            environ_overrides={'REMOTE_ADDR': '203.0.113.43'},
        )
        for _ in range(11)
    ]

    assert [response.status_code for response in responses[:10]] == [503] * 10
    assert responses[10].status_code == 429


def test_anonymous_review_submissions_are_rejected_before_validation(application_client):
    response = application_client.post('/review-submit', json={
        'booking_id': 1,
        'rating': 5,
        'comment': 'x' * 3001,
    })

    assert response.status_code == 401
    assert 'error' in response.get_json()


def test_review_pages_are_readable_without_an_account(application_client):
    response = application_client.get('/reviews?target_type=tour&target_id=not-a-tour')

    assert response.status_code == 200
    assert response.get_json()['reviews'] == []
    assert response.get_json()['summary'] == {'rating': 0, 'review_count': 0}


@pytest.mark.parametrize('url', [
    'file:///etc/passwd',
    'http://open.er-api.com/v6/latest/KES',
    'https://attacker.example/data',
])
def test_currency_fetch_rejects_untrusted_urls(url):
    with pytest.raises(ValueError, match='URL is not allowed'):
        application._fetch_json(url)


def test_catalog_image_upload_uses_configured_persistent_storage_in_production(monkeypatch, tmp_path):
    monkeypatch.setattr(application, 'IS_PRODUCTION', True)
    monkeypatch.setattr(application, 'UPLOAD_DIR', str(tmp_path))
    monkeypatch.setenv('UPLOAD_DIR', str(tmp_path))
    image = b'\x89PNG\r\n\x1a\n' + b'\x00' * 8

    with application.app.test_request_context(
        '/api/vendor/uploads',
        method='POST',
        data={'image': (io.BytesIO(image), 'harbor.png')},
    ):
        response, status_code = application.save_catalog_image('vendors/1')

    assert status_code == 201
    stored_path = tmp_path / response['image_url'].removeprefix('uploads/')
    assert stored_path.read_bytes() == image

    served = application.app.test_client().get(f"/{response['image_url']}")
    assert served.status_code == 200
    assert served.data == image


def test_catalog_image_upload_requires_persistent_storage_in_production(monkeypatch):
    monkeypatch.setattr(application, 'IS_PRODUCTION', True)
    monkeypatch.delenv('UPLOAD_DIR', raising=False)

    with application.app.test_request_context('/api/vendor/uploads', method='POST'):
        response, status_code = application.save_catalog_image('vendors/1')

    assert status_code == 503
    assert 'persistent image storage' in response['error']


def test_catalog_image_upload_stays_disabled_on_vercel(monkeypatch, tmp_path):
    monkeypatch.setenv('VERCEL', '1')
    monkeypatch.setenv('UPLOAD_DIR', str(tmp_path))
    monkeypatch.setattr(application, 'IS_PRODUCTION', True)
    monkeypatch.setattr(application, 'UPLOAD_DIR', str(tmp_path))

    with application.app.test_request_context('/api/vendor/uploads', method='POST'):
        response, status_code = application.save_catalog_image('vendors/1')

    assert status_code == 503


@pytest.mark.parametrize('url', [
    '/images/../app.py',
    '/pictures/../app.py',
    '/uploads/../app.py',
])
def test_asset_routes_do_not_expose_source_files(application_client, url):
    response = application_client.get(url)

    assert response.status_code in {403, 404}
    assert b'import ' not in response.data
