import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_vercel_config_builds_frontend_and_includes_flask_assets():
    config = json.loads((PROJECT_ROOT / 'vercel.json').read_text())

    assert config['$schema'] == 'https://openapi.vercel.sh/vercel.json'
    assert config['buildCommand'] == 'npm --prefix frontend ci && npm --prefix frontend run build'
    assert config['functions']['app.py']['includeFiles'] == (
        '{frontend/dist/**,images/**,pictures/**,templates/**,*.html,*.css,*.js,*.svg}'
    )


def test_vercel_ignore_excludes_secrets_and_ephemeral_data():
    ignored = (PROJECT_ROOT / '.vercelignore').read_text().splitlines()

    assert '.env' in ignored
    assert '.env.*' in ignored
    assert 'uploads' in ignored
    assert 'tests' in ignored
