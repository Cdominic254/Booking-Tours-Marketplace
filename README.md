# Lamu Tours & Booking Agency

Booking and tour-management website for Lamu. Flask serves the application pages and APIs, while the React/Vite frontend is built as part of deployment.

## Features

- Tour discovery, availability, bookings, and customer booking lookup
- Admin and vendor portals, catalogue management, and reviews
- Safaricom Daraja M-Pesa STK Push payments
- Contact submissions, optional email notifications, and currency conversion

## Tech Stack

- Python 3.12, Flask, Flask-SQLAlchemy, and Gunicorn
- React 19 and Vite 6
- Vercel Functions for the Flask app, with hosted PostgreSQL and Redis

## Local Development

Use Python 3.12+ and Node.js 22+. In one terminal, create a virtual environment and start Flask:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt pytest
SECRET_KEY=dev-only-secret DATABASE_URL=sqlite:///submissions.db RATELIMIT_STORAGE_URI=memory:// SITE_URL=http://127.0.0.1:5000 PORT=5000 python app.py
```

In a second terminal, start Vite:

```bash
npm --prefix frontend ci
npm --prefix frontend run dev
```

Open the Vite URL printed in the terminal. The Vite development server proxies API requests to Flask on port 5000. Run the backend test suite with `pytest`.

## Configuration

Production settings are listed in `.env.example`. The app requires a persistent `SECRET_KEY`, PostgreSQL `DATABASE_URL`, and shared Redis `RATELIMIT_STORAGE_URI` when `SITE_URL` is HTTPS or `FLASK_ENV=production`. Daraja and email integrations are optional until configured. Never commit `.env` or put payment credentials in a URL.

Tour bookings are paid in KES through Safaricom Daraja Lipa Na M-Pesa Online. A booking remains pending until the payment callback is checked against Daraja's STK Query API; a browser redirect is not proof of payment. Test successful, cancelled, and timed-out payments with sandbox credentials before switching `DARAJA_ENV` to `production`.

## Testing

```bash
pytest
```

## Vercel Deployment

Connect this GitHub repository to Vercel with the repository root as the project root. Vercel detects the root Flask `app.py`; `vercel.json` builds the Vite frontend and bundles the HTML templates and image assets used by Flask.

Configure these production and preview environment variables in the Vercel project settings:

- `SECRET_KEY`: long, random session-signing key
- `DATABASE_URL`: persistent external PostgreSQL connection string
- `RATELIMIT_STORAGE_URI`: external Redis connection URL
- `FLASK_ENV=production`
- `SITE_URL`: canonical HTTPS site URL
- `DARAJA_ENV=sandbox` and Daraja credentials/callback URL while testing
- Email settings if contact and booking emails are required

Vercel's function filesystem is ephemeral. Do not configure SQLite or `UPLOAD_DIR`; image upload endpoints intentionally return 503 on Vercel until persistent object storage is integrated. Bundled `images/` and `pictures/` assets continue to serve normally. Verify `/healthz`, `/readyz`, page navigation, booking, and Daraja callbacks after deployment.

### CI/CD

GitHub Actions runs the backend tests and frontend build before the gated Vercel deployment job. To enable deployments, add repository secrets `VERCEL_TOKEN`, `VERCEL_ORG_ID`, and `VERCEL_PROJECT_ID`, then set the repository variable `VERCEL_DEPLOY_ENABLED=true`.

Push to `main` for production. Same-repository pull requests create preview deployments; fork pull requests run CI only.
