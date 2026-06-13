# Vaishnavi Gaushala — Django Backend

Server-rendered Django backend for [Vaishnavi Gau Seva Gausansthan](https://vaishnavigss.com/) —
a small Indian gaushala that funds the care of 35+ indigenous cows by selling
A2 dairy, traditional sweets, and panchgavya products.

## Stack

- **Django 5.2 LTS** + **Pillow** — the only application dependencies.
- **PostgreSQL** in production, **SQLite** in dev (controlled via `DJANGO_SETTINGS_MODULE`).
- **WhiteNoise** + **gunicorn** + **psycopg[binary]** — production-only infra.
- Server-rendered templates, Bootstrap 5 (CDN), GSAP 3 (CDN), vanilla JS. No React, no SPA.
- No DRF, no Razorpay SDK, no Celery, no Redis, no allauth, no third-party Django packages
  beyond the infrastructure above.

External services (all reached via stdlib `urllib`):

| Service | What for | Setup |
|---|---|---|
| Razorpay | Payments, webhooks | [README → Phase 6 setup](#phase-6--cart-checkout-razorpay-payments) |
| Postmark / AWS SES | Transactional email | [README → Email setup](#email-setup-postmark-recommended) |
| MSG91 | OTP SMS (India, DLT) | [README → SMS setup](#sms-setup-msg91--india-dlt-compliant) |

## Quick start (local dev)

```powershell
git clone <repo-url> vaishnavi-backend
cd vaishnavi-backend

python -m venv .venv
.\.venv\Scripts\Activate.ps1                # PowerShell
# source .venv/bin/activate                 # macOS / Linux

pip install -r requirements.txt

python manage.py migrate
python manage.py create_dev_superuser       # admin / admin123  (dev only)
python manage.py load_initial_data          # categories, breeds, plans, FAQs

python manage.py runserver
```

Visit:
- Homepage — http://127.0.0.1:8000/
- Admin — http://127.0.0.1:8000/admin/

Dev defaults: SQLite, console email, locmem cache, OTPs print to console.
`vaishnavi.settings.dev` is the default settings module for `manage.py`.

For Razorpay payment testing in dev, copy `.env.example` to `.env` and fill in
your test keys (see "Phase 6" section below).

## Project layout

```
vaishnavi-backend/
├── manage.py
├── requirements.txt                (5 entries — Django, Pillow + 3 infra libs)
├── .env.example
├── README.md
├── deploy/                         (production runbook + configs)
│   ├── DEPLOY.md                   ← full deployment guide
│   ├── nginx.conf
│   ├── vaishnavi.service           (gunicorn systemd unit)
│   ├── crontab.txt
│   └── scripts/
│       ├── backup_db.sh
│       └── backup_media.sh
├── scripts/
│   └── bootstrap_production.sh
├── vaishnavi/                      (project settings + URLs)
│   ├── settings/                   (split: base.py / dev.py / prod.py)
│   ├── urls.py
│   ├── wsgi.py                     (defaults to prod settings)
│   └── asgi.py                     (defaults to prod settings)
├── core/                           (homepage, contact, FAQs, SEO, healthz)
├── catalog/                        (products, categories, variants)
├── accounts/                       (users, addresses, OTPs, profile)
├── orders/                         (cart, checkout, orders, invoices)
├── subscriptions/                  (plans, subscriptions, deliveries, payments)
├── services/                       (gaushala services, visit booking)
├── templates/                      (HTML + email templates)
├── static/                         (CSS, JS, SVG, images, JSON)
└── media/                          (user uploads — empty by default)
```

## Deployment

See **[deploy/DEPLOY.md](deploy/DEPLOY.md)** for the full Ubuntu 22.04 runbook
(server setup, gunicorn, nginx, Let's Encrypt, cron, backups, going-live checklist).

For local Postgres testing before deploy, see the "Test against Postgres locally"
section further down.

## Phase history

The project shipped in 8 incremental phases. Each phase has its own
behavior — see git log for details.

| Phase | Scope |
|---|---|
| 1 | Scaffolding, homepage, partials, static asset copy |
| 2 | Models (catalog, breeds, cows, products, variants, FAQs, settings) |
| 3 | Public pages — product list/detail, services, about, contact, 404 |
| 4 | Authentication — register, login, OTP, profile, addresses |
| 5 | Inquiry forms — contact, newsletter, adoption, wholesale, hampers, visit, subscription inquiry |
| 6 | Cart, checkout, Razorpay payments, COD, GST invoices, order management |
| 7 | Subscriptions — signup, renewal, lifecycle (pause/resume/cancel), cron, daily delivery roster |
| 8 | Production readiness — settings split, Postgres, security hardening, email/SMS providers, SEO, deployment runbook |

---

## Phase 6 — Cart, Checkout, Razorpay payments

### Razorpay setup (test mode)

1. Sign up at **https://razorpay.com**.
2. Dashboard → **Settings → API Keys** → click **Generate Test Key**.
3. Copy `.env.example` → `.env` and paste your `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`.
4. The `.env` file is git-ignored. Never commit real keys.

Switch to **live keys** when going to production: same env-var names, with
`rzp_live_...` IDs. No code change needed.

### Test cards (Razorpay test mode)

| Card | Result |
|---|---|
| `4111 1111 1111 1111` · any future expiry · any CVV · OTP `123456` | Success |
| `5104 0600 0000 0008` · any future expiry · any CVV | Success (Mastercard) |
| UPI: `success@razorpay` | Success |
| UPI: `failure@razorpay` | Failed payment |

Full list: https://razorpay.com/docs/payments/payments/test-card-details/

### Webhook setup for local development

The browser callback (`/cart/checkout/callback/`) handles the happy path.
Webhooks are the safety net for "user closed the tab after paying" — and must
be tested with a public URL.

```powershell
# Install ngrok once
choco install ngrok           # or download from https://ngrok.com/download

# Expose the dev server publicly
ngrok http 8000

# Razorpay Dashboard → Settings → Webhooks → Add New Webhook
#   URL:    https://<your-ngrok-id>.ngrok-free.app/cart/checkout/webhook/razorpay/
#   Events: payment.captured, payment.failed
#   Secret: generate one, copy into .env as RAZORPAY_WEBHOOK_SECRET
```

### Promo codes

Three demo codes are seeded into the dev DB by `load_initial_data`:
`VAISHNAVI10` (10%), `FIRSTORDER` (₹100 off), `GAUSEVA` (5%). Manage more in
Admin → **Orders → Promo codes**. Codes are stored upper-case;
`PromoCode.is_valid()` checks active flag, date range, max-uses, min-order-amount.

---

## Phase 7 — Subscriptions

Self-serve subscriptions: pay with Razorpay for the first billing period,
receive scheduled deliveries, skip / pause / cancel from profile, renew via
email reminder. **No auto-debit** — every renewal is a fresh Razorpay one-time
payment, triggered by the customer clicking "Renew now" in the reminder.

### Subscription cron jobs

Four daily commands keep subscriptions healthy. Install via
[deploy/crontab.txt](deploy/crontab.txt):

| Command | What it does |
|---|---|
| `expire_unpaid_subscriptions` | ACTIVE + period ended (no cancel) → **EXPIRED** + email; CANCELLED + period ended → **ENDED** (silent) |
| `auto_resume_paused` | PAUSED + `paused_until` passed → ACTIVE, restores future PAUSED deliveries to SCHEDULED |
| `mark_missed_deliveries` | SCHEDULED + date ≤ yesterday → MISSED |
| `send_renewal_reminders` | Emails customers whose period ends in 5 / 3 / 1 days. Idempotent via cache key with 30-day TTL. `--dry-run` flag available. |

### Daily delivery roster (admin)

For the milk delivery team. **Admin → Subscription deliveries → "View today's
roster"** or `/admin/subscriptions/subscriptiondelivery/roster/`. Groups by
pincode then by Morning/Evening window; print-clean via `@media print`.

### Profile views

Customers manage subscriptions from `/account/profile/subscriptions/` (list)
and `/account/profile/subscriptions/<sub_no>/` (detail with pause/resume/cancel
/renew/change-address buttons gated by status).

---

## Phase 8 — Production readiness

### Settings split

```
vaishnavi/settings/
├── __init__.py       (marker — pick base/dev/prod via DJANGO_SETTINGS_MODULE)
├── base.py           (env-agnostic: apps, middleware, templates, auth, i18n)
├── dev.py            (SQLite, console email, locmem cache, no SSL — default for manage.py)
└── prod.py           (Postgres, SMTP, DB cache, WhiteNoise, full HTTPS hardening)
```

`manage.py` defaults to `vaishnavi.settings.dev`. `wsgi.py` and `asgi.py`
default to `vaishnavi.settings.prod`. Override with `DJANGO_SETTINGS_MODULE=...`
in `.env` or the shell.

### Email setup (Postmark recommended)

1. Sign up at [postmarkapp.com](https://postmarkapp.com) (or AWS SES).
2. Verify your sending domain — add SPF, DKIM, DMARC DNS records.
3. Postmark dashboard → Servers → API Tokens → SMTP Credentials. With
   Postmark the **username and password are the same server token**.
4. Add to production `.env`:
   ```
   EMAIL_HOST=smtp.postmarkapp.com
   EMAIL_PORT=587
   EMAIL_HOST_USER=<postmark-server-token>
   EMAIL_HOST_PASSWORD=<postmark-server-token>
   EMAIL_USE_TLS=True
   DEFAULT_FROM_EMAIL=Vaishnavi Gaushala <hello@vaishnavigss.com>
   ```
5. Test from the prod shell:
   ```python
   from django.core.mail import send_mail
   send_mail('Test', 'It works', 'hello@vaishnavigss.com', ['you@example.com'])
   ```

**AWS SES variant**: `EMAIL_HOST=email-smtp.<region>.amazonaws.com`,
`EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD` from IAM SES SMTP credentials (not
your AWS access keys).

In dev, email continues to print to the console.

### SMS setup (MSG91 — India DLT-compliant)

1. Sign up at [msg91.com](https://msg91.com).
2. Complete **DLT registration** (one-time, 2–5 business days):
   - Register your business entity with a DLT operator.
   - Register an SMS template for OTP. Body must match what `send_sms_otp`
     would write (variables are flow parameters).
3. From the dashboard, copy: `AUTH_KEY`, `SENDER_ID` (6 chars), `TEMPLATE_ID`.
4. Add to `.env`:
   ```
   MSG91_AUTH_KEY=<your-auth-key>
   MSG91_SENDER_ID=<6-char-approved-id>
   MSG91_OTP_TEMPLATE_ID=<template-id from MSG91>
   ```
5. Test with a fresh phone registration on the production server.

In dev with `MSG91_AUTH_KEY` empty, `send_sms_otp` prints to console — no
change to development workflow.

### Test against Postgres locally (recommended before deploy)

```powershell
# 1. Install Postgres (one-time)
#    Windows: https://www.postgresql.org/download/windows/
#    macOS:   brew install postgresql && brew services start postgresql
#    Ubuntu:  sudo apt install postgresql

# 2. Create a dev DB + user
psql -U postgres -c "CREATE USER vaishnavi_dev WITH PASSWORD 'dev_pw';"
psql -U postgres -c "CREATE DATABASE vaishnavi_dev_pg OWNER vaishnavi_dev;"

# 3. Set env vars + run migrations against Postgres
$env:DJANGO_SETTINGS_MODULE = "vaishnavi.settings.prod"
$env:SECRET_KEY = "dev-prod-test-secret-key-not-for-real-deploy"
$env:DB_NAME = "vaishnavi_dev_pg"
$env:DB_USER = "vaishnavi_dev"
$env:DB_PASSWORD = "dev_pw"
$env:DB_HOST = "127.0.0.1"
$env:ALLOWED_HOSTS = "localhost,127.0.0.1,testserver"

python manage.py migrate
python manage.py createcachetable
python manage.py load_initial_data
python manage.py create_dev_superuser
python manage.py check --deploy
```

To browse a Postgres-backed instance without HTTPS, create a one-off
`vaishnavi/settings/local_postgres.py` that imports from `prod` and flips
`DEBUG=True`, `SECURE_SSL_REDIRECT=False`, `SESSION_COOKIE_SECURE=False`,
`CSRF_COOKIE_SECURE=False`. The `local_settings.py` pattern is already
git-ignored.

### Health check + SEO endpoints

| URL | Purpose |
|---|---|
| `/healthz/` | JSON `{"status": "ok"}` + 200 on DB connectivity; 503 otherwise. Use for load-balancer health checks. |
| `/robots.txt` | Dynamic — sitemap URL pulled from `SITE_DOMAIN`. |
| `/sitemap.xml` | Static pages + every active product, category, and self-serve subscription plan. |

JSON-LD: every page emits `LocalBusiness` schema; product detail pages emit
`Product` + `Offer` (INR). Per-page `og:*` and `twitter:*` blocks override the
base defaults.

### Going to production

See **[deploy/DEPLOY.md](deploy/DEPLOY.md)** — full Ubuntu 22.04 runbook including
gunicorn systemd, nginx config, Let's Encrypt, crontab install, backup setup,
restore drill, and the going-live checklist.

---

## License & contact

All rights reserved by Vaishnavi Gau Seva Gausansthan.

Maintainer contact: see `SiteSettings.email_primary` in admin (defaults to
`seva@vaishnavigss.com`).
