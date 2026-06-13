# Vaishnavi Gaushala — Production Deployment

Target: **Ubuntu 22.04 LTS** VPS (Digital Ocean / Hetzner / Linode / AWS Lightsail).

- Minimum: 2 GB RAM, 2 vCPU, 40 GB SSD.
- Recommended: 4 GB RAM, 2 vCPU, 80 GB SSD.
- Domain pointed to the server's public IPv4 via an `A` record (and `AAAA` for IPv6 if available).

The runbook below assumes you're starting from a blank VPS. Subsequent
deployments take ~2 minutes (see "Subsequent deployments" near the end).

---

## One-time server setup

### 1. Update system, install dependencies

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
    python3.11 python3.11-venv python3-pip \
    postgresql postgresql-contrib \
    nginx \
    certbot python3-certbot-nginx \
    git rsync \
    ufw
```

Enable firewall:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable
```

### 2. Create the application user

```bash
sudo adduser vaishnavi --disabled-password --gecos ""
sudo usermod -aG www-data vaishnavi
```

### 3. Create the PostgreSQL role + database

```bash
# Generate a strong DB password and save it — you'll paste it into .env next.
DB_PW=$(openssl rand -base64 32)
echo "DB password (save this!): $DB_PW"

sudo -u postgres psql <<EOF
CREATE USER vaishnavi WITH PASSWORD '$DB_PW';
CREATE DATABASE vaishnavi_prod OWNER vaishnavi;
GRANT ALL PRIVILEGES ON DATABASE vaishnavi_prod TO vaishnavi;
EOF
```

### 4. Clone the repo as the `vaishnavi` user

```bash
sudo -u vaishnavi -i
cd ~
git clone <repo-url> vaishnavi-backend
cd vaishnavi-backend

python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Configure `.env`

```bash
cp .env.example .env
nano .env
```

Fill in:

- **`SECRET_KEY`** — `python -c "import secrets; print(secrets.token_urlsafe(60))"`
- **`DJANGO_SETTINGS_MODULE=vaishnavi.settings.prod`**
- **`ALLOWED_HOSTS=vaishnavigss.com,www.vaishnavigss.com`** (your real domain)
- **`SITE_DOMAIN=https://vaishnavigss.com`**
- **`DB_NAME`/`DB_USER`/`DB_PASSWORD`/`DB_HOST`/`DB_PORT`** — from step 3.
- **`EMAIL_*`** — Postmark / SES SMTP credentials (see README "Email setup").
- **`DEFAULT_FROM_EMAIL=Vaishnavi Gaushala <hello@vaishnavigss.com>`**
- **`SERVER_EMAIL=errors@vaishnavigss.com`** (where 500-error reports go)
- **`ADMIN_EMAIL=admin@vaishnavigss.com`** (recipient for ERROR-level logs)
- **`MSG91_*`** — once DLT registration is approved (see README "SMS setup").
- **`RAZORPAY_*`** — start with test keys until KYC; flip to `rzp_live_*` after.

Save and close.

### 6. Bootstrap the database + collect static files

```bash
./scripts/bootstrap_production.sh
```

This runs `migrate`, `createcachetable`, `collectstatic`, `load_initial_data`,
and prompts for a superuser. About 30 seconds total.

### 7. Install the gunicorn systemd service

```bash
exit   # back to your sudo-capable user

sudo cp /home/vaishnavi/vaishnavi-backend/deploy/vaishnavi.service \
        /etc/systemd/system/vaishnavi.service
sudo systemctl daemon-reload
sudo systemctl enable vaishnavi
sudo systemctl start vaishnavi
sudo systemctl status vaishnavi    # should report "active (running)"
```

Tail the logs to confirm gunicorn is happy:

```bash
sudo journalctl -u vaishnavi -f
```

### 8. Install nginx

```bash
sudo cp /home/vaishnavi/vaishnavi-backend/deploy/nginx.conf \
        /etc/nginx/sites-available/vaishnavigss
sudo ln -s /etc/nginx/sites-available/vaishnavigss \
           /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t       # syntax check
sudo systemctl reload nginx
```

At this point `http://vaishnavigss.com` should reach gunicorn (still on port 80).

### 9. Issue Let's Encrypt certificate

```bash
sudo certbot --nginx -d vaishnavigss.com -d www.vaishnavigss.com
```

Follow the prompts: provide an admin email, agree to TOS, choose redirect HTTP→HTTPS.

Certbot rewrites the nginx config to add SSL. Test:

```bash
curl -I https://vaishnavigss.com
```

Renewal is automatic via `certbot.timer` (installed by the certbot package).

### 10. Install the crontab

```bash
sudo -u vaishnavi crontab /home/vaishnavi/vaishnavi-backend/deploy/crontab.txt
sudo -u vaishnavi crontab -l    # verify
```

The 4 Phase 7 subscription jobs, the OTP cleanup, and the nightly backups are
now scheduled.

### 11. Configure Razorpay webhook

In the Razorpay dashboard → Settings → Webhooks → Add new webhook:

- **URL:** `https://vaishnavigss.com/cart/checkout/webhook/razorpay/`
- **Events:** `payment.captured`, `payment.failed`
- **Secret:** generate a long random string, paste it into `.env` as
  `RAZORPAY_WEBHOOK_SECRET`, then restart gunicorn:
  ```bash
  sudo systemctl restart vaishnavi
  ```

Test by sending a webhook from the dashboard's "Test Webhook" button — should
return `200 OK` and log to `logs/app.log`.

### 12. After 24 hours of clean HTTPS operation: bump HSTS

Edit `.env`:

```
SECURE_HSTS_SECONDS=31536000
```

Then restart gunicorn:

```bash
sudo systemctl restart vaishnavi
```

After another week, consider submitting to [hstspreload.org](https://hstspreload.org).
To do so, you must first set `SECURE_HSTS_PRELOAD=True` in
[vaishnavi/settings/prod.py](../vaishnavi/settings/prod.py).

---

## Subsequent deployments

```bash
sudo -u vaishnavi -i
cd ~/vaishnavi-backend
git pull
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
exit
sudo systemctl restart vaishnavi
```

If the deploy includes a `requirements.txt` change or a migration, also tail
`journalctl -u vaishnavi -f` to confirm the restart was clean.

---

## Monitoring

| What | Where |
|---|---|
| App logs (INFO+) | `tail -f /home/vaishnavi/vaishnavi-backend/logs/app.log` |
| Gunicorn errors | `tail -f /home/vaishnavi/vaishnavi-backend/logs/gunicorn-error.log` |
| Gunicorn access | `tail -f /home/vaishnavi/vaishnavi-backend/logs/gunicorn-access.log` |
| Cron output | `tail -f /home/vaishnavi/vaishnavi-backend/logs/cron.log` |
| Backup status | `tail -f /home/vaishnavi/logs/backup.log` |
| Nginx access | `sudo tail -f /var/log/nginx/access.log` |
| Nginx errors | `sudo tail -f /var/log/nginx/error.log` |
| Systemd journal | `sudo journalctl -u vaishnavi -n 100 --no-pager` |
| Health check | `curl https://vaishnavigss.com/healthz/` |

500-level errors are emailed to `ADMIN_EMAIL` via Django's `AdminEmailHandler`
(set in `vaishnavi/settings/base.py`'s LOGGING config).

---

## Backups

Nightly:

- `2:00 AM` → `backup_db.sh` writes a gzipped `pg_dump` to `~/backups/db/`
  (14-day retention, pruned by the script itself).
- `2:30 AM` → `backup_media.sh` rsyncs `media/` to `~/backups/media/`.

### Offsite backup (strongly recommended)

The local backups protect against accidental DELETE / DROP, but not against
the VPS itself dying. Layer an offsite copy:

```bash
sudo apt install rclone
rclone config       # interactive — set up B2 / S3 / Google Drive

# Add to vaishnavi user's crontab:
0 4 * * * rclone sync /home/vaishnavi/backups remote:vaishnavi-backups >> /home/vaishnavi/logs/offsite.log 2>&1
```

[Backblaze B2](https://www.backblaze.com/b2/) is the cheapest option — ~$6/TB/month —
and has rclone first-class support.

### Restore drill

Do this once before going live. Pick a recent dump and confirm the round-trip:

```bash
# Spin up a throwaway DB
sudo -u postgres createdb vaishnavi_restore_test

# Restore
gunzip < ~/backups/db/vaishnavi_<date>.sql.gz \
  | psql -h 127.0.0.1 -U vaishnavi vaishnavi_restore_test

# Spot-check: should see your data
psql -h 127.0.0.1 -U vaishnavi vaishnavi_restore_test \
     -c "SELECT count(*) FROM catalog_product;"

# Clean up
sudo -u postgres dropdb vaishnavi_restore_test
```

---

## Going-live checklist

Before announcing the site publicly:

- [ ] Real product photos uploaded via admin
- [ ] Real cow photos uploaded
- [ ] `SiteSettings` row: real phone, email, WhatsApp, address, business hours
- [ ] `SiteSettings`: **real GSTIN, real FSSAI license** (mandatory for invoice display)
- [ ] Per-product `hsn_code` and `gst_rate` filled in (defaults are placeholders)
- [ ] Shipping rates configured: `shipping_ncr_charge`, `shipping_other_charge`,
      `free_shipping_threshold`, `ncr_pincode_prefixes`
- [ ] Real founder bio + photo on About page
- [ ] Razorpay account in **LIVE mode** (KYC complete)
- [ ] Razorpay webhook URL configured in dashboard + secret in `.env`
- [ ] Postmark / SES domain verified, sending working (test from shell)
- [ ] MSG91 DLT registration complete, OTP template approved, test SMS arrives
- [ ] At least 5 real test orders placed + refunded successfully (end-to-end)
- [ ] Subscription signup tested for each tier (daily milk, monthly ghee, quarterly)
- [ ] Custom 404 / 403 / 500 pages render correctly
- [ ] `/sitemap.xml` submitted to Google Search Console + Bing Webmaster Tools
- [ ] Analytics installed (Google Analytics 4 or Plausible — outside this scope)
- [ ] Backup script tested with a restore drill (see "Backups" above)
- [ ] `og-default.jpg` (1200×630 brand image) uploaded to `static/img/`
- [ ] Bumped `SECURE_HSTS_SECONDS=31536000` after 24h of clean HTTPS
- [ ] Replaced `full-plate` plan handling — set `is_self_serve=False` OR
      finished plan-items (Phase 7 quirk)

---

## Rollback

For a code rollback:

```bash
sudo -u vaishnavi -i
cd ~/vaishnavi-backend
git log --oneline -10        # find the last good commit
git checkout <commit-sha>
source .venv/bin/activate
python manage.py migrate     # may need: python manage.py migrate <app> <last_good_migration>
python manage.py collectstatic --noinput
exit
sudo systemctl restart vaishnavi
```

For a database rollback:

```bash
# Stop the app first so no writes land during restore.
sudo systemctl stop vaishnavi

# Drop and recreate
sudo -u postgres dropdb vaishnavi_prod
sudo -u postgres createdb vaishnavi_prod -O vaishnavi

# Restore from last good backup
gunzip < /home/vaishnavi/backups/db/vaishnavi_<date>.sql.gz \
  | psql -h 127.0.0.1 -U vaishnavi vaishnavi_prod

sudo systemctl start vaishnavi
```

A code rollback alone (without DB rollback) is safe as long as no migrations
were applied. With migrations, you need a matching DB restore or a manual
backward migration.

---

## Alternative: PaaS deployment

If managing a VPS is too much, [Railway](https://railway.app),
[Render](https://render.com), [Fly.io](https://fly.io), and AWS App Runner all
support Django + Postgres deployments via Dockerfile or buildpacks. Trade-off:
less ops work, higher cost at scale, less control.

For Railway specifically:

1. Connect the GitHub repo.
2. Add the Postgres plugin → `DATABASE_URL` is auto-injected. Map it via a
   small `prod_railway.py` settings module that parses the URL into the
   `DATABASES['default']` dict, or use `dj-database-url` (which would need to
   be added to requirements — break with the "no extra libraries" policy
   only if you choose this path).
3. Set every other `.env` var in the Railway dashboard.
4. Add a `Procfile`:
   ```
   web: gunicorn vaishnavi.wsgi:application
   release: python manage.py migrate && python manage.py createcachetable && python manage.py collectstatic --noinput
   ```
5. For cron: use Railway's cron addon, pointing at the same `manage.py` commands.

We can build a proper PaaS variant in a separate phase if you go that route —
nothing in the current settings split blocks it.

---

## Quick reference

| Action | Command |
|---|---|
| Bounce the app | `sudo systemctl restart vaishnavi` |
| Tail the app | `sudo journalctl -u vaishnavi -f` |
| Reload nginx | `sudo systemctl reload nginx` |
| Renew SSL manually | `sudo certbot renew` |
| Run a one-off cron job | `sudo -u vaishnavi DJANGO_SETTINGS_MODULE=vaishnavi.settings.prod /home/vaishnavi/vaishnavi-backend/.venv/bin/python /home/vaishnavi/vaishnavi-backend/manage.py <command>` |
| Django shell on prod | `sudo -u vaishnavi DJANGO_SETTINGS_MODULE=vaishnavi.settings.prod /home/vaishnavi/vaishnavi-backend/.venv/bin/python /home/vaishnavi/vaishnavi-backend/manage.py shell` |
| Edit `.env` | `sudo -u vaishnavi nano /home/vaishnavi/vaishnavi-backend/.env` then `sudo systemctl restart vaishnavi` |
