import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request


class PaystackError(RuntimeError):
    def __init__(self, message, *, outcome_unknown=False):
        super().__init__(message)
        self.outcome_unknown = outcome_unknown


_PAYSTACK_HOST = 'api.paystack.co'
_CHECKOUT_HOST = 'checkout.paystack.com'
_WEBHOOK_TOLERANCE_SECONDS = 300


def _configuration():
    secret_key = os.environ.get('PAYSTACK_SECRET_KEY', '').strip()
    site_url = os.environ.get('SITE_URL', '').strip().rstrip('/')
    callback_url = (
        os.environ.get('PAYSTACK_CALLBACK_URL', '').strip()
        or f'{site_url}/paystack/callback'
    )
    if not secret_key.startswith('sk_'):
        raise PaystackError('Paystack payment configuration is incomplete.')
    if not callback_url:
        raise PaystackError('Paystack payment configuration is incomplete.')

    callback = urllib.parse.urlparse(callback_url)
    callback_host = (callback.hostname or '').lower()
    is_local_host = callback_host in {'localhost'} or callback_host.endswith(
        ('.localhost', '.local', '.internal')
    )
    try:
        is_local_host = is_local_host or not ipaddress.ip_address(callback_host).is_global
    except ValueError:
        pass
    if callback.scheme != 'https' or not callback.netloc or is_local_host:
        raise PaystackError('PAYSTACK_CALLBACK_URL must be a publicly reachable HTTPS URL.')
    return {'secret_key': secret_key, 'callback_url': callback_url}


def is_configured():
    try:
        _configuration()
    except PaystackError:
        return False
    return True


def new_reference(prefix):
    safe_prefix = re.sub(r'[^A-Za-z0-9-]', '', str(prefix))[:16] or 'PAY'
    return f'KB-{safe_prefix}-{secrets.token_hex(16)}'


def _request_json(config, path, *, method='GET', payload=None, outcome_unknown=False):
    if not path.startswith('/transaction/'):
        raise PaystackError('Paystack URL is not allowed.', outcome_unknown=outcome_unknown)

    data = None if payload is None else json.dumps(payload).encode('utf-8')
    request = urllib.request.Request(
        f'https://{_PAYSTACK_HOST}{path}',
        data=data,
        method=method,
        headers={
            'Authorization': f"Bearer {config['secret_key']}",
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
    )
    try:
        # The URL is restricted to Paystack's HTTPS host immediately above.
        with urllib.request.urlopen(request, timeout=15) as response:  # nosec B310
            result = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        try:
            details = json.loads(exc.read().decode('utf-8'))
            message = details.get('message') or 'Paystack rejected the request.'
        except (UnicodeDecodeError, json.JSONDecodeError):
            message = 'Paystack rejected the request.'
        raise PaystackError(
            str(message),
            outcome_unknown=outcome_unknown and exc.code >= 500,
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise PaystackError(
            'Paystack could not be reached.', outcome_unknown=outcome_unknown
        ) from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PaystackError(
            'Paystack returned an invalid response.', outcome_unknown=outcome_unknown
        ) from exc

    if not isinstance(result, dict) or result.get('status') is not True:
        message = result.get('message') if isinstance(result, dict) else None
        raise PaystackError(
            str(message or 'Paystack rejected the request.'),
            outcome_unknown=outcome_unknown,
        )
    transaction = result.get('data')
    if not isinstance(transaction, dict):
        raise PaystackError(
            'Paystack returned an invalid response.', outcome_unknown=outcome_unknown
        )
    return transaction


def initialize_transaction(*, email, amount, reference, metadata):
    config = _configuration()
    transaction = _request_json(
        config,
        '/transaction/initialize',
        method='POST',
        payload={
            'email': email,
            # Paystack expects KES in cents, not whole shillings.
            'amount': int(amount) * 100,
            'currency': 'KES',
            'reference': reference,
            'callback_url': config['callback_url'],
            'metadata': metadata,
        },
        outcome_unknown=True,
    )
    authorization_url = transaction.get('authorization_url')
    access_code = transaction.get('access_code')
    checkout = urllib.parse.urlparse(authorization_url or '')
    if (
        transaction.get('reference') != reference
        or not isinstance(access_code, str)
        or not access_code
        or checkout.scheme != 'https'
        or checkout.hostname != _CHECKOUT_HOST
    ):
        raise PaystackError(
            'Paystack accepted the payment but did not return a valid checkout.',
            outcome_unknown=True,
        )
    return {
        'reference': reference,
        'authorization_url': authorization_url,
        'access_code': access_code,
        'customer_message': 'Continue to the secure Paystack checkout to complete your payment.',
    }


def verify_transaction(reference):
    config = _configuration()
    transaction = _request_json(
        config,
        f'/transaction/verify/{urllib.parse.quote(str(reference), safe="")}',
        outcome_unknown=True,
    )
    if transaction.get('reference') != reference:
        raise PaystackError('Paystack verification returned a different transaction.')
    return transaction


def _legacy_signature_matches(raw_body, signature):
    secret_key = os.environ.get('PAYSTACK_SECRET_KEY', '').strip()
    if not secret_key.startswith('sk_') or not re.fullmatch(r'[0-9a-fA-F]{128}', signature or ''):
        return False
    expected = hmac.new(secret_key.encode('utf-8'), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature.lower())


def _current_signature_matches(raw_body, header, now=None):
    secrets_to_try = [
        value.strip()
        for value in os.environ.get('PAYSTACK_WEBHOOK_SECRET', '').split(',')
        if value.strip().startswith('whsec_')
    ]
    if not secrets_to_try or not header:
        return False

    timestamp = None
    signatures = []
    for part in header.split(','):
        key, separator, value = part.strip().partition('=')
        if not separator:
            continue
        if key == 't':
            if timestamp is not None or not value.isdigit():
                return False
            timestamp = int(value)
        elif key == 'v1':
            key_id, separator, signature = value.partition(':')
            if separator and key_id.startswith('whk_'):
                signatures.append(signature)
    if timestamp is None or not signatures:
        return False
    now = int(time.time()) if now is None else now
    if abs(now - timestamp) > _WEBHOOK_TOLERANCE_SECONDS:
        return False

    signed_content = f'{timestamp}.'.encode('ascii') + raw_body
    for secret in secrets_to_try:
        expected = hmac.new(secret.encode('utf-8'), signed_content, hashlib.sha512).hexdigest()
        for signature in signatures:
            if not re.fullmatch(r'[0-9a-f]{128}', signature):
                continue
            if hmac.compare_digest(expected, signature):
                return True
    return False


def verify_webhook_signature(raw_body, legacy_header='', current_header='', *, now=None):
    return _legacy_signature_matches(raw_body, legacy_header) or _current_signature_matches(
        raw_body, current_header, now=now
    )
