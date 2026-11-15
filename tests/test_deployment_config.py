import json
import os
import subprocess
import sys
from pathlib import Path

import app as application


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_vercel_config_builds_frontend_and_includes_flask_assets():
    config = json.loads((PROJECT_ROOT / 'vercel.json').read_text())

    assert config['$schema'] == 'https://openapi.vercel.sh/vercel.json'

    # Vercel rejects top-level build and function settings once services are in
    # use, so the Flask app owns the build for the whole deployment.
    service = config['services']['web']
    assert service['root'] == '.'
    assert service['framework'] == 'flask'
    assert service['buildCommand'] == 'npm --prefix frontend ci && npm --prefix frontend run build'
    function = service['functions']['app.py']
    assert function['maxDuration'] == 60
    assert function['includeFiles'] == (
        '{frontend/dist/**,images/**,pictures/**,saas/**,logo.svg}'
    )
    for excluded in ('tests/**', 'docs/**', 'frontend/node_modules/**', 'frontend/src/**', '*.db'):
        assert excluded in function['excludeFiles']

    # Services stay internal until a top-level rewrite routes public traffic to
    # them, so the catch-all rule is what makes the site reachable at all.
    assert config['rewrites'] == [
        {'source': '/(.*)', 'destination': {'service': 'web'}}
    ]


def test_vercel_ignore_excludes_secrets_and_ephemeral_data():
    ignored = (PROJECT_ROOT / '.vercelignore').read_text().splitlines()

    assert '.env' in ignored
    assert '.env.*' in ignored
    assert 'uploads' in ignored
    assert 'tests' in ignored
    assert 'docs' in ignored
    assert 'pytest-of-*' in ignored


def test_static_assets_are_cached_for_the_cdn():
    client = application.app.test_client()

    logo = client.get('/logo.svg')
    assert logo.status_code == 200
    assert logo.headers['Cache-Control'] == 'public, max-age=86400'
    assert logo.headers['Vercel-CDN-Cache-Control'] == 'public, max-age=86400'

    image_name = next((PROJECT_ROOT / 'images').iterdir()).name
    image = client.get(f'/images/{image_name}')
    assert image.status_code == 200
    assert 'max-age=86400' in image.headers['Cache-Control']

    page = client.get('/healthz')
    assert page.status_code == 200
    assert 'Cache-Control' not in page.headers


def test_app_boots_on_vercel_without_secret_key_or_database_url():
    env = {
        **os.environ,
        'VERCEL': '1',
        'SECRET_KEY': '',
        'DATABASE_URL': '',
        'RATELIMIT_STORAGE_URI': '',
    }

    result = subprocess.run(
        [sys.executable, '-c', 'import app; print(app.RATE_LIMIT_STORAGE_URI)'],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert 'WARNING: DATABASE_URL is not set' in result.stderr
    assert 'WARNING: SECRET_KEY is not set' in result.stderr
    assert 'WARNING: rate limiting falls back' in result.stderr


def test_app_trusts_the_vercel_proxy_headers():
    env = {
        **os.environ,
        'VERCEL': '1',
        'DATABASE_URL': 'sqlite:////tmp/kenyabook-proxy-test.db',
        'SECRET_KEY': 'deployment-test-secret',
        'RATELIMIT_STORAGE_URI': 'memory://',
    }

    result = subprocess.run(
        [
            sys.executable,
            '-c',
            'import app; print(type(app.app.wsgi_app).__name__)',
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert 'ProxyFix' in result.stdout
