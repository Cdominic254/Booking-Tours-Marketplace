"""Live chat: visitor threads, admin replies, and CSRF-protected moderation."""

import uuid

import pytest

import app as application


@pytest.fixture
def chat_client():
    def clear():
        with application.app.app_context():
            application.ChatMessage.query.delete(synchronize_session=False)
            application.ChatConversation.query.delete(synchronize_session=False)
            application.db.session.commit()

    clear()
    yield application.app.test_client()
    clear()


@pytest.fixture
def admin_headers():
    email = f'chat-test-{uuid.uuid4().hex}@example.test'
    with application.app.app_context():
        admin = application.AdminAccount(
            name='Chat agent',
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


def test_visitor_message_starts_a_thread_and_polls_for_replies(chat_client):
    response = chat_client.post('/api/support/chat', json={
        'body': 'Do you run private safaris?',
        'name': '  Amina  ',
        'email': 'AMINA@example.test',
        'page': '/tours.html',
    })
    assert response.status_code == 201

    payload = response.get_json()
    assert len(payload['token']) == 32
    assert payload['status'] == 'open'
    assert payload['name'] == 'Amina'
    assert payload['email'] == 'amina@example.test'
    assert [message['sender'] for message in payload['messages']] == ['visitor']

    token = payload['token']
    first_id = payload['messages'][0]['id']

    same_thread = chat_client.get('/api/support/chat', headers={'X-Chat-Token': token})
    assert same_thread.status_code == 200
    assert len(same_thread.get_json()['messages']) == 1

    follow_up = chat_client.post('/api/support/chat', json={'token': token, 'body': 'Also, is lunch included?'})
    assert follow_up.status_code == 201
    assert len(follow_up.get_json()['messages']) == 2

    # Polling with the last seen id only returns what is new.
    after = chat_client.get(f'/api/support/chat?after={first_id}', headers={'X-Chat-Token': token})
    assert [message['body'] for message in after.get_json()['messages']] == ['Also, is lunch included?']


def test_unknown_or_malformed_tokens_start_a_clean_thread(chat_client):
    for header in ('f' * 32, 'not-a-token', ''):
        response = chat_client.get('/api/support/chat', headers={'X-Chat-Token': header})
        assert response.status_code == 200
        payload = response.get_json()
        assert payload['token'] == ''
        assert payload['messages'] == []


def test_chat_rejects_empty_messages(chat_client):
    for payload in ({}, {'body': '   '}, {'body': '\n\t'}):
        response = chat_client.post('/api/support/chat', json=payload)
        assert response.status_code == 400, payload
        assert response.get_json()['error'] == 'Type a message before sending.'

    with application.app.app_context():
        assert application.ChatConversation.query.count() == 0


def test_chat_rejects_plain_text_posts(chat_client):
    response = chat_client.post('/api/support/chat', data='hello', content_type='text/plain')
    assert response.status_code == 400
    assert response.get_json()['error'] == 'Chat messages must be sent as JSON.'


def test_admin_reply_reaches_the_visitor(chat_client, admin_headers):
    admin_client, headers = admin_headers
    visitor = chat_client.post('/api/support/chat', json={
        'body': 'Is the Mara trip suitable for children?',
        'name': 'Guest',
    }).get_json()
    token = visitor['token']

    assert chat_client.get('/api/admin/chat').status_code == 401

    listing = admin_client.get('/api/admin/chat').get_json()
    assert listing['unread_count'] == 1
    conversation = next(item for item in listing['conversations'] if item['preview'] == 'Is the Mara trip suitable for children?')
    assert conversation['staff_unread'] == 1
    assert conversation['name'] == 'Guest'

    thread = admin_client.get(f"/api/admin/chat/{conversation['id']}")
    assert thread.status_code == 200
    assert [message['sender'] for message in thread.get_json()['messages']] == ['visitor']

    # Reading the thread clears the unread badge.
    assert admin_client.get('/api/admin/chat').get_json()['unread_count'] == 0

    without_csrf = admin_client.post(f"/api/admin/chat/{conversation['id']}", json={'body': 'Yes, children are welcome.'})
    assert without_csrf.status_code == 403

    reply = admin_client.post(
        f"/api/admin/chat/{conversation['id']}",
        json={'body': 'Yes, children are welcome.'},
        headers=headers,
    )
    assert reply.status_code == 201
    assert reply.get_json()['message']['sender'] == 'staff'
    assert reply.get_json()['message']['author'] == 'Chat agent'

    seen = chat_client.get('/api/support/chat', headers={'X-Chat-Token': token}).get_json()
    assert [message['sender'] for message in seen['messages']] == ['visitor', 'staff']
    assert seen['messages'][1]['body'] == 'Yes, children are welcome.'


def test_admin_can_close_reopen_and_the_visitor_reopens_again(chat_client, admin_headers):
    admin_client, headers = admin_headers
    visitor = chat_client.post('/api/support/chat', json={'body': 'Can I pay on arrival?'}).get_json()

    conversation_id = admin_client.get('/api/admin/chat?status=all').get_json()['conversations'][0]['id']

    closed = admin_client.post(f'/api/admin/chat/{conversation_id}', json={'action': 'close'}, headers=headers)
    assert closed.status_code == 200
    assert closed.get_json()['conversation']['status'] == 'closed'
    assert admin_client.get('/api/admin/chat').get_json()['open_count'] == 0

    reopened = admin_client.post(f'/api/admin/chat/{conversation_id}', json={'action': 'reopen'}, headers=headers)
    assert reopened.get_json()['conversation']['status'] == 'open'

    admin_client.post(f'/api/admin/chat/{conversation_id}', json={'action': 'close'}, headers=headers)
    chat_client.post('/api/support/chat', json={'token': visitor['token'], 'body': 'One more question'})
    thread = admin_client.get(f'/api/admin/chat/{conversation_id}').get_json()
    assert thread['conversation']['status'] == 'open'
    assert thread['conversation']['message_count'] == 2


def test_admin_endpoints_validate_targets(chat_client, admin_headers):
    admin_client, headers = admin_headers

    missing = admin_client.get('/api/admin/chat/999999')
    assert missing.status_code == 404
    assert missing.get_json()['error'] == 'That conversation no longer exists.'

    visitor = chat_client.post('/api/support/chat', json={'body': 'Hello there'}).get_json()
    assert visitor['token']
    conversation_id = admin_client.get('/api/admin/chat?status=all').get_json()['conversations'][0]['id']

    empty = admin_client.post(f'/api/admin/chat/{conversation_id}', json={'body': '  '}, headers=headers)
    assert empty.status_code == 400
    assert empty.get_json()['error'] == 'Type a reply before sending.'
