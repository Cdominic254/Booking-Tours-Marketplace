# Lamu Tours & Booking Agency

Booking and tour-management website for Lamu. Flask provides the API and production server, while the React/Vite frontend is built into `frontend/dist` for deployment.

## Features

- Tour discovery, availability, bookings, and customer booking lookup
- Admin and vendor portals, catalogue management, and reviews
- Safaricom Daraja M-Pesa STK Push payments
- Contact submissions, optional email notifications, and currency conversion
- Bundled Lamu image assets served from `/images` and `/pictures`

## Tech Stack

- Python 3.12, Flask, Flask-SQLAlchemy, and Gunicorn
- React 19 and Vite 6
- Vercel Functions for the Flask app, with hosted PostgreSQL and Redis

## Project Structure

- `app.py` — Flask application, API routes, authentication, bookings, payments, and asset serving
- `saas/` — SQLAlchemy models and booking/payment services
- `frontend/src/` — React application and UI components
- `frontend/vite.config.js` — Vite development server and Flask API proxy
- `images/` and `pictures/` — bundled catalogue and destination images
- `tests/` — backend, deployment, payment, booking, and security tests

## Local Development

Use Python 3.12+ and Node.js 22+. From the repository root, create a virtual environment and install the backend dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest
```

Start Flask in one terminal:

```bash
SECRET_KEY=dev-only-secret \
DATABASE_URL=sqlite:///submissions.db \
RATELIMIT_STORAGE_URI=memory:// \
SITE_URL=http://127.0.0.1:5000 \
PORT=5000 python app.py
```

Start Vite in a second terminal:

```bash
npm --prefix frontend ci
npm --prefix frontend run dev
```

Open the Vite URL printed in the terminal, normally `http://127.0.0.1:5173`. The Vite development server proxies `/api`, authentication, booking, review, and image requests to Flask on port 5000.

## Configuration

Production settings are listed in `.env.example`. A persistent `SECRET_KEY`, PostgreSQL `DATABASE_URL`, and shared Redis `RATELIMIT_STORAGE_URI` are required for a healthy production deployment, but the app still boots when they are missing and logs a `WARNING` at startup instead of refusing to serve: session signatures are derived from `DATABASE_URL` (or a random key when that is unavailable), the database falls back to ephemeral SQLite, and rate limits become per-instance. Daraja and email integrations are optional until configured. Never commit `.env` or put payment credentials in a URL.

For local development, SQLite and the in-memory rate limiter are supported. They are not suitable for production or multiple application instances.

Tour bookings are paid in KES through Safaricom Daraja Lipa Na M-Pesa Online. A booking remains pending until the payment callback is checked against Daraja's STK Query API; a browser redirect is not proof of payment. Test successful, cancelled, and timed-out payments with sandbox credentials before switching `DARAJA_ENV` to `production`.

## Testing

```bash
pytest
npm --prefix frontend run build
python -m bandit -r app.py saas -q
```

The test suite covers authentication rate limits, CSRF protection, access control, booking ownership, payment verification, upload validation, deployment configuration, and path traversal protection.

## Vercel Deployment

Connect this GitHub repository to Vercel with the repository root as the project root. `vercel.json` builds the Vite frontend and bundles `frontend/dist`, `images`, `pictures`, `saas`, and `logo.svg` with the Flask function in `app.py`.

Configure these production and preview environment variables in the Vercel project settings:

- `SECRET_KEY`: long, random session-signing key
- `DATABASE_URL`: persistent external PostgreSQL connection string
- `RATELIMIT_STORAGE_URI`: external Redis connection URL
- `FLASK_ENV=production`
- `SITE_URL`: canonical HTTPS site URL
- `DARAJA_ENV=sandbox` and Daraja credentials/callback URL while testing
- Email settings if contact and booking emails are required

Vercel's function filesystem is ephemeral. Do not configure SQLite or `UPLOAD_DIR`; without `DATABASE_URL` the function boots on ephemeral SQLite under `/tmp` and every cold start loses bookings and accounts, and image upload endpoints intentionally return 503 on Vercel until persistent object storage is integrated. Bundled `images/` and `pictures/` assets continue to serve normally. Verify `/healthz`, `/readyz`, page navigation, booking, and Daraja callbacks after deployment.

### CI/CD

GitHub Actions runs the backend tests and frontend build before the gated Vercel deployment job. To enable deployments, add repository secrets `VERCEL_TOKEN`, `VERCEL_ORG_ID`, and `VERCEL_PROJECT_ID`, then set the repository variable `VERCEL_DEPLOY_ENABLED=true`.

Push to `main` for production. Same-repository pull requests create preview deployments; fork pull requests run CI only.

## Security Notes

- Set a long, random `SECRET_KEY` in every deployed environment.
- Use HTTPS in production and enable secure session cookies.
- Keep PostgreSQL and Redis credentials outside the repository.
- Daraja callback URLs must be public HTTPS URLs; payment success is confirmed through Daraja verification, not a browser redirect.
- Uploads require an authenticated admin or vendor session, CSRF protection, safe filenames, and validated image signatures.
- Do not expose the development SQLite database, `.env`, or upload directory publicly.
