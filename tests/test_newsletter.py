"""Newsletter signup: one row per address, validated, and surfaced to admins."""

import pytest

import app as application

TEST_PREFIX = 'newsletter-test-'


@pytest.fixture
def newsletter_client():
    with application.app.app_context():
        application.NewsletterSubscriber.query.filter(
            application.NewsletterSubscriber.email.like(f'{TEST_PREFIX}%')
        ).delete(synchronize_session=False)
        application.db.session.commit()
    yield application.app.test_client()
    with application.app.app_context():
        application.NewsletterSubscriber.query.filter(
            application.NewsletterSubscriber.email.like(f'{TEST_PREFIX}%')
        ).delete(synchronize_session=False)
        application.db.session.commit()


def test_newsletter_signup_is_stored_once(newsletter_client):
    email = f'{TEST_PREFIX}Guest@Example.test'

    response = newsletter_client.post('/api/newsletter', json={'email': email, 'source': 'footer'})
    assert response.status_code == 201
    assert response.get_json()['already_subscribed'] is False

    duplicate = newsletter_client.post('/api/newsletter', json={'email': email.lower(), 'source': 'home'})
    assert duplicate.status_code == 200
    assert duplicate.get_json()['already_subscribed'] is True

    with application.app.app_context():
        rows = application.NewsletterSubscriber.query.filter_by(email=email.lower()).all()
        assert len(rows) == 1
        # The first signup keeps the source it came from; a repeat never rewrites it.
        assert rows[0].source == 'footer'
        assert rows[0].is_active is True


def test_newsletter_signup_accepts_form_posts_and_unsubscribes_quietly(newsletter_client):
    email = f'{TEST_PREFIX}form@example.test'
    response = newsletter_client.post('/api/newsletter', data={'email': email, 'source': 'journal'})
    assert response.status_code == 201

    with application.app.app_context():
        subscriber = application.NewsletterSubscriber.query.filter_by(email=email).one()
        assert subscriber.source == 'journal'
        subscriber.is_active = False
        application.db.session.commit()

    # Signing up again after removal reactivates the same row.
    again = newsletter_client.post('/api/newsletter', json={'email': email, 'source': 'footer'})
    assert again.status_code == 200
    with application.app.app_context():
        subscribers = application.NewsletterSubscriber.query.filter_by(email=email).all()
        assert len(subscribers) == 1
        assert subscribers[0].is_active is True
        assert subscribers[0].source == 'footer'


def test_newsletter_rejects_bad_addresses(newsletter_client):
    for payload in ({}, {'email': ''}, {'email': 'not-an-email'}, {'email': 'a@b'}, {'email': 'two words@example.test'}):
        response = newsletter_client.post('/api/newsletter', json=payload)
        assert response.status_code == 400, payload
        assert response.get_json()['error'] == 'Enter a valid email address.'

    with application.app.app_context():
        assert application.NewsletterSubscriber.query.filter(
            application.NewsletterSubscriber.email.like(f'{TEST_PREFIX}%')
        ).count() == 0
