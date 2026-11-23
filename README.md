# kenyaBook

**Live application:** [booking-tours-marketplace.vercel.app](https://booking-tours-marketplace.vercel.app) - tours, safaris, and stays across ten Kenyan destinations.

Booking and tour-management website for Kenya-wide travel, trading as **kenyaBook** at [kenyabook.com](https://kenyabook.com). **SafariNaStay** is the official brand slogan and social media identity (`@safarinasstay` on Instagram, Facebook, X, TikTok and YouTube). Lamu is one of eight bookable destinations (alongside Mombasa, Diani, Watamu, Nairobi, Lake Naivasha, the Maasai Mara, and Amboseli) rather than the subject of the whole site. Flask provides the API and production server, while the React/Vite frontend is built into `frontend/dist` for deployment.

## Features

- Tour discovery, destination filtering, availability, bookings, and customer booking lookup
- Admin and partner portals, catalogue management, and reviews
- Paystack hosted checkout for domestic and international bookings and partner subscriptions
- Contact submissions, optional email notifications, and currency conversion
- Bundled destination image assets served from `/images` and `/pictures`

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

Open the Vite URL printed in the terminal, normally `http://127.0.0.1:5173`. The Vite development server proxies `/api`, authentication, booking, Paystack callback, review, and image requests to Flask on port 5000.

## Configuration

Production settings are listed in `.env.example`. A persistent `SECRET_KEY`, PostgreSQL `DATABASE_URL`, and shared Redis `RATELIMIT_STORAGE_URI` are required for a healthy production deployment, but the app still boots when they are missing and logs a `WARNING` at startup instead of refusing to serve: session signatures are derived from `DATABASE_URL` (or a random key when that is unavailable), the database falls back to ephemeral SQLite, and rate limits become per-instance. Paystack and email integrations are optional until configured. Never commit `.env` or put payment credentials in a URL.

For local development, SQLite and the in-memory rate limiter are supported. They are not suitable for production or multiple application instances.

Tour and accommodation bookings, including international travelers' bookings, are paid in KES through Paystack's hosted checkout. Kenyan and international customers use the same booking flow and are redirected directly to Paystack after seats or room nights are reserved. A booking remains pending until Paystack verifies the transaction reference, KES currency, and exact amount. A browser redirect is never treated as proof of payment. International card acceptance must also be enabled for the live Paystack account.

For Paystack, set `PAYSTACK_SECRET_KEY` to the server-side secret key and `PAYSTACK_CALLBACK_URL` to the public HTTPS callback URL (it defaults to `${SITE_URL}/paystack/callback`). Configure `https://<your-domain>/paystack/webhook` in the Paystack dashboard. The webhook accepts both legacy `x-paystack-signature` HMAC signatures made with the secret key and current timestamped `Paystack-Signature` values made with `PAYSTACK_WEBHOOK_SECRET`. Aged pending transactions are rechecked when their status is polled or a partner retries renewal; only provider-confirmed terminal results release reserved capacity or clear a renewal blocker. Test successful, failed, abandoned, duplicate, and replayed events with Paystack test keys before switching to live keys.

Customers can cancel requested or confirmed bookings online up to the cancellation window saved in admin settings (48 hours before departure or check-in by default). Cancelling a paid booking releases the held tour seats or room nights and queues a full refund automatically; refunds are sent manually outside the app and an administrator marks them paid in the admin portal. Refunds are tracked with a status (`none`, `pending`, `paid`, `rejected`), amount, reason, and request/payout timestamps.

Discovery is data-driven rather than static. Verified (paid) bookings, guest ratings and published room rates feed every listing: `/api/catalogue`, `/api/search` and `/api/recommendations` expose a rating, review count, lifetime and 30-day booking counts, a starting price (the cheapest active room for stays), a price comparison against comparable listings, and `Top rated` / `Popular` / `Best value` badges. Search keeps text relevance first, adds a capped data boost so equally relevant listings are ordered by real demand and value, and supports `sort=relevance|price_low|price_high|rating|popular`. `/api/recommendations` returns similar listings when given a `slug` (same destination, style and price range) and trending listings otherwise, excluding the current result set. The admin operations payload adds a `price_insights` block with median prices, listings above or below the area average and paid revenue per listing.

## Testing

```bash
pytest
npm --prefix frontend run build
python -m bandit -r app.py saas -q
```

The test suite covers authentication rate limits, CSRF protection, access control, booking ownership, payment verification, upload validation, deployment configuration, and path traversal protection.

## Vercel Deployment

Production runs at [https://booking-tours-marketplace.vercel.app](https://booking-tours-marketplace.vercel.app), built and promoted from the `Booking-Tours-Marketplace` branch. Connect this GitHub repository to Vercel with the repository root as the project root, which also gives every push and pull request its own preview URL. `vercel.json` declares a single `web` service with its root at `.`: it builds the Vite frontend, sets a 60-second function timeout, and bundles `frontend/dist`, `images`, `pictures`, `saas`, and `logo.svg` with the Flask function in `app.py` while excluding tests, docs, local databases, and `frontend/node_modules`/`frontend/src` from the bundle. A catch-all `rewrites` rule sends every request to that service, because services stay internal until a top-level rewrite routes public traffic to them. Build and function settings live inside the service rather than at the top level, which Vercel rejects once `services` is present. Python 3.12 is pinned by `.python-version`.

Configure these production and preview environment variables in the Vercel project settings:

- `SECRET_KEY`: long, random session-signing key
- `DATABASE_URL`: persistent external PostgreSQL connection string
- `RATELIMIT_STORAGE_URI`: external Redis connection URL
- `FLASK_ENV=production`
- `SITE_URL`: canonical HTTPS site URL
- `PAYSTACK_SECRET_KEY`, `PAYSTACK_CALLBACK_URL`, and optionally `PAYSTACK_WEBHOOK_SECRET` for Paystack
- Email settings if contact and booking emails are required

Vercel's function filesystem is ephemeral. Do not configure SQLite or `UPLOAD_DIR`; without `DATABASE_URL` the function boots on ephemeral SQLite under `/tmp` and every cold start loses bookings and accounts, and image upload endpoints intentionally return 503 on Vercel until persistent object storage is integrated. Bundled `images/` and `pictures/` assets continue to serve normally. Verify `/healthz`, `/readyz`, page navigation, domestic and international booking checkout, and Paystack callbacks/webhooks after deployment.

On Vercel the app trusts the edge's `X-Forwarded-*` headers, so rate limits key on the visitor IP instead of the proxy address; set `TRUST_PROXY_HEADERS=true` to opt in behind another reverse proxy. Hashed bundles under `/assets/` are served with a one-year immutable cache and bundled photography for one day, both of which the Vercel CDN honours, so repeat visits do not invoke the function for static files. Before the first deploy, run `python -m pytest` and `npm --prefix frontend run build`, then confirm `DATABASE_URL`, `SECRET_KEY`, `RATELIMIT_STORAGE_URI`, `PAYSTACK_CALLBACK_URL`, and the Paystack webhook URL point at the production hostname.

### CI/CD

GitHub Actions runs the backend tests and frontend build on every push. Deployments are handled by Vercel's GitHub integration, which is connected to this repository, so leave the optional `deploy-vercel` job disabled: setting the repository variable `VERCEL_DEPLOY_ENABLED=true` together with the `VERCEL_TOKEN`, `VERCEL_ORG_ID`, and `VERCEL_PROJECT_ID` secrets would deploy a second time for the same commit.

Push to `main` or the `Booking-Tours-Marketplace` branch for production. Same-repository pull requests create preview deployments; fork pull requests run CI only.

Two guards keep local, remote, and deployed state aligned. The `deploy-vercel` job fails when its checkout has uncommitted changes or does not match the triggering commit, and the `production-drift` job compares the newest production deployment against the pushed commit, failing when production is running a commit that git does not hold. Both exist because deploying from a dirty working tree once left production on code that no commit contained, and the next push silently reverted it. Deploy by hand with `scripts/deploy.sh`, which exits unless the tree is clean and `HEAD` matches `origin`; that is the case CI can never check, because a GitHub runner always starts with a clean tree.

## Security Notes

- Set a long, random `SECRET_KEY` in every deployed environment.
- Use HTTPS in production and enable secure session cookies.
- Keep PostgreSQL and Redis credentials outside the repository.
- The Paystack callback URL must be a public HTTPS URL; payment success is confirmed through server-side verification, not a browser redirect.
- Keep `PAYSTACK_SECRET_KEY` and `PAYSTACK_WEBHOOK_SECRET` server-side, and reject webhooks whose signatures do not match.
- Uploads require an authenticated admin or partner session, CSRF protection, safe filenames, and validated image signatures.
- Do not expose the development SQLite database, `.env`, or upload directory publicly.

## License

Released under the MIT License; see [LICENSE](LICENSE). The application code, tests, and
documentation are covered by it. The photography bundled in `images/` and `pictures/` depicts real
Kenyan destinations and operators and is not relicensed here.
