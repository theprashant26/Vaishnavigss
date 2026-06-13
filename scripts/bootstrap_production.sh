#!/usr/bin/env bash
# Bootstrap a production deployment from a fresh checkout.
# Assumes: venv exists at .venv, .env is filled with real values,
# Postgres database and role exist, and the server user can reach them.

set -euo pipefail

cd "$(dirname "$0")/.."

source .venv/bin/activate
export DJANGO_SETTINGS_MODULE=vaishnavi.settings.prod

echo "==> [1/5] Running migrations..."
python manage.py migrate --noinput

echo "==> [2/5] Creating cache table..."
python manage.py createcachetable

echo "==> [3/5] Collecting static files..."
python manage.py collectstatic --noinput

echo "==> [4/5] Seeding initial data (categories, breeds, plans, FAQs, settings)..."
python manage.py load_initial_data

echo "==> [5/5] Creating superuser (interactive)..."
python manage.py createsuperuser

echo
echo "Bootstrap complete."
echo "Next: configure nginx, install the gunicorn systemd service, and install crontab."
echo "See deploy/DEPLOY.md for the full runbook."
