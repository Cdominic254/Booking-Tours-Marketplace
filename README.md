# Lamu Tours & Booking Agency

Booking and tour-management website for Lamu. Flask serves the application pages and APIs; the production image builds and serves the React/Vite frontend alongside the legacy HTML pages.

## Features

- Tour discovery, availability, bookings, and customer booking lookup
- Admin and vendor portals, catalogue management, and reviews
- Safaricom Daraja M-Pesa STK Push payments
- Contact submissions, optional email notifications, and currency conversion

## Tech Stack

- Python 3.12, Flask, Flask-SQLAlchemy, and Gunicorn
- React 19 and Vite 6
- PostgreSQL for application data and Redis for shared rate-limit state
- Vercel Functions for the Flask app, with external PostgreSQL and Redis
- Docker Compose and Caddy for the Oracle VM deployment option

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

### Terraform and CI/CD

Terraform provisions the Vercel project; GitHub Actions deploys only after backend tests, frontend build, and Terraform validation pass.

1. Create a Vercel API token, then run from the repository root:

   ```bash
   cd infra/vercel
   read -s -p 'Vercel API token: ' TF_VAR_vercel_api_token
   export TF_VAR_vercel_api_token
   terraform init
   terraform plan
   terraform apply
   unset TF_VAR_vercel_api_token
   terraform output -raw vercel_project_id
   ```

   Keep the Terraform state private. The token is supplied through the environment and must not be committed.
2. Set the production/preview environment variables in Vercel. Run `npx vercel@latest link` from the repository root; read `orgId` and `projectId` from `.vercel/project.json`.
3. Add GitHub secrets `VERCEL_TOKEN`, `VERCEL_ORG_ID`, and `VERCEL_PROJECT_ID`. Set repository variable `VERCEL_DEPLOY_ENABLED=true` to enable the gated deployment job.
4. Push to `main` for production. Same-repository pull requests create preview deployments; fork pull requests run CI only.

## Oracle Cloud VM Deployment

For a self-managed option, the app also has a Docker Compose stack with Flask, PostgreSQL, Redis, and Caddy. Persistent volumes hold database, rate-limit, certificate, and upload data. The free Oracle VM has no automatic off-site backups or uptime guarantee; schedule backups and apply security updates.
