import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_vercel_config_builds_frontend_and_includes_flask_assets():
    config = json.loads((PROJECT_ROOT / 'vercel.json').read_text())

    assert config['$schema'] == 'https://openapi.vercel.sh/vercel.json'
    assert config['buildCommand'] == 'npm --prefix frontend ci && npm --prefix frontend run build'
    assert config['functions']['app.py']['includeFiles'] == (
        '{frontend/dist/**,images/**,pictures/**,saas/**,logo.svg}'
    )


def test_vercel_ignore_excludes_secrets_and_ephemeral_data():
    ignored = (PROJECT_ROOT / '.vercelignore').read_text().splitlines()

    assert '.env' in ignored
    assert '.env.*' in ignored
    assert 'uploads' in ignored
    assert 'tests' in ignored


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
