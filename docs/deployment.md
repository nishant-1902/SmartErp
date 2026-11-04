# Production deployment

## Development and production settings

The backend uses `SMARTERP_ENV` in `backend/config/settings.py` rather than
separate settings modules:

- **Development** is the default. `DEBUG` defaults to true, local hosts are
  allowed, HTTPS redirection and HSTS default off, and logging goes to the
  console. Use this only on a trusted development machine.
- **Production** requires `SMARTERP_ENV=production`, `DEBUG=False`, explicit
  non-wildcard `ALLOWED_HOSTS`, strong unique Django/JWT secrets, and a
  configured MongoDB URI/database. Invalid production configuration stops
  Django from starting. Secure refresh/session/CSRF cookies, HTTPS redirection,
  one-year HSTS, security headers, and rotating file logs are on by default.

The production file logger defaults to `backend/logs/smarterp.log`, rotates at
10 MiB, and keeps five backups. Set `LOG_FILE` to a writable persistent path
outside the application checkout in production. Protect and retain those logs
according to your organization's policy. Do not log passwords, tokens,
connection URIs, or customer data.

| Variable | Development | Production |
|---|---|---|
| `SMARTERP_ENV` | `development` | `production` |
| `DEBUG` | `True` | `False` (required) |
| `SECRET_KEY` | Local-only secret | Unique secret, at least 50 characters |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Exact public API hostnames; no `*` |
| `MONGO_URI`, `MONGO_DB_NAME` | Local authenticated replica set | Private authenticated replica set/cluster |
| `JWT_SECRET_KEY` | Local-only secret | Separate unique secret, at least 32 characters |
| `CORS_ALLOWED_ORIGINS` | Exact local frontend origin | Exact HTTPS frontend origins; no wildcard |
| `REFRESH_COOKIE_SECURE` | May be false for local HTTP | Always true |
| `SECURE_SSL_REDIRECT` | False | True; only disable for local plaintext smoke tests |
| `SECURE_HSTS_SECONDS` | 0 | Defaults to 31,536,000; must be positive |
| `TRUST_X_FORWARDED_PROTO` | False | True only behind a trusted TLS-terminating proxy |
| `LOG_FILE` | `backend/logs/smarterp.log` | Writable persistent protected file path |
| `LOG_MAX_BYTES`, `LOG_BACKUP_COUNT`, `LOG_LEVEL` | Defaults | Tune for host storage and retention |

Copy `backend/.env.example` to an ignored `backend/.env`. Supply real secrets
through a protected environment/secret manager or a file readable only by the
service account. Never commit `.env` or paste secret values into command lines,
tickets, or logs. MongoDB URI reserved characters in credentials must be
percent-encoded. The `MONGO_TEST_URI` must use a separate dedicated test
database/user and must never point at production.

Production password-reset email delivery is **not configured**. The reset
service intentionally refuses to issue a reset when `DEBUG=False`; integrate
and test a trusted mail provider before enabling production password resets.
Development reset URLs are logged only in development and contain a
single-use secret; treat local logs as sensitive.

## Local production-settings smoke test on Windows

Gunicorn does not run on Windows. Use the already-installed Waitress WSGI
server for a local production-settings check. This uses HTTP only to verify
startup and the health endpoint; secure cookies will not be sent over HTTP,
and HSTS is only emitted on HTTPS responses. Do not use this exception in a
real deployment.

In PowerShell, first configure `backend/.env` with valid local MongoDB
credentials and strong non-placeholder Django/JWT keys, then:

```powershell
Set-Location backend
$env:SMARTERP_ENV = "production"
$env:DEBUG = "False"
$env:ALLOWED_HOSTS = "127.0.0.1,localhost"
$env:SECURE_SSL_REDIRECT = "False"
.\venv\Scripts\waitress-serve.exe --listen=127.0.0.1:8000 config.wsgi:application
```

In another PowerShell window:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/health/
```

Never use `python manage.py runserver` in production.

## Linux API service with Gunicorn

The pinned dependency is installed only on non-Windows platforms. Create a
dedicated Linux service account, deploy the backend code and virtual
environment, set a private `EnvironmentFile`, and run Gunicorn on loopback
behind a reverse proxy:

```bash
cd /srv/smarterp/backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
SMARTERP_ENV=production ./venv/bin/python manage.py check
SMARTERP_ENV=production ./venv/bin/python manage.py init_db
SMARTERP_ENV=production ./venv/bin/gunicorn config.wsgi:application \
  --bind 127.0.0.1:8000 --workers 3 \
  --access-logfile - --error-logfile -
```

Example systemd unit (adjust paths, account, and worker count for the host):

```ini
[Unit]
Description=SmartERP API
After=network.target

[Service]
User=smarterp
Group=smarterp
WorkingDirectory=/srv/smarterp/backend
Environment=SMARTERP_ENV=production
EnvironmentFile=/etc/smarterp/backend.env
ExecStart=/srv/smarterp/backend/venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3 --access-logfile - --error-logfile -
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Keep `/etc/smarterp/backend.env` owned by root and readable only by the
service account. Do not set `DEBUG=True`. Use a process supervisor (such as
systemd), not a terminal session, to keep the service running.

## TLS reverse proxy and frontend static hosting

Terminate HTTPS at a maintained reverse proxy such as Caddy or nginx, or use
static hosting/CDN plus a separate API host. These services have different
cost, operational-control, and maintenance trade-offs; select one according
to your security and availability needs. Use a certificate from a trusted
certificate authority (for example, Let's Encrypt where applicable).

Example nginx routing shape:

```nginx
server {
    listen 443 ssl;
    server_name erp.example.com;

    root /srv/smarterp/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

Set `TRUST_X_FORWARDED_PROTO=True` only when the API is reachable solely
through a trusted proxy that overwrites `X-Forwarded-Proto`. Django then
recognizes proxy HTTPS, applies HTTPS redirects correctly, and emits HSTS.
Do not trust forwarded headers from arbitrary clients.

Build the static frontend with the public API origin set **before** the build:

```powershell
Set-Location frontend
$env:VITE_API_BASE_URL = "https://api.example.com/api"
npm ci
npm run build
```

Vite substitutes `VITE_*` values into the generated JavaScript at build time.
They are public, inspectable by every browser user, and cannot be changed by
editing the server environment after the build. Never place passwords, JWT
keys, or other secrets in `VITE_*` values. Upload `frontend/dist/` to a static
host or web server and configure all client-side routes to fall back to
`index.html` (for example, nginx `try_files` above). The production web server
does not need Node.js. Do not use Vite's development server as a production
static host.

For split frontend/API domains, set CORS to the exact frontend origin and
retain credentialed requests only for required cookie flows. Prefer frontend
and API subdomains under the same site. If a truly cross-site refresh cookie
is needed, configure `SameSite=None; Secure` and implement/verify the required
CSRF defenses before release. Never use wildcard CORS with credentials.

## MongoDB network and initialization

- Use an authenticated MongoDB replica set because purchase/stock/sales
  workflows require transactions.
- Keep the database on a private network. Allow database traffic only from
  application hosts and approved administrative networks; never expose
  MongoDB directly to the public Internet.
- Use a least-privilege application user scoped to the application database.
  Use a separate test account and database.
- Review duplicate data before creating new unique indexes. Run the
  repeatable initializer during a controlled release:

  ```bash
  cd /srv/smarterp/backend
  SMARTERP_ENV=production ./venv/bin/python manage.py init_db
  ```

- Check replica-set primary/health and application connectivity using secure
  administrative access. The public `/api/health/` endpoint is only a liveness
  endpoint; it does not prove MongoDB is available.

## Backup, restore, and operations

From the repository root on Windows, `.\scripts\backup-db.ps1` uses the
configured backend MongoDB URI, creates a timestamped compressed dump under
`backups\`, and removes its temporary credentials file afterward. Install
MongoDB Database Tools (`mongodump`/`mongorestore`) and keep backup directories
encrypted and access-controlled. Back up files off-host according to the
required recovery-point objective; a successful dump alone is not proof of
recoverability.

For restore, use `mongorestore` with the matching private test or recovery
cluster URI and the `--gzip` option. Restore into an isolated database/cluster
first, verify expected collections/indexes and application workflows, and
document the restoration result before relying on the backup. Never test a
restore against the production database.

Monitor API process health, MongoDB availability/replica-set state, disk
space, backup age, error rates, and log rotation. Use an error-tracking service
only after reviewing data scrubbing and retention. Alert on repeated API
errors and failed backups. The rotating Django log defaults to 10 MiB x five
files; adapt it to host capacity and central log shipping/retention. Do not
log bearer/refresh tokens, reset URLs, passwords, MongoDB URIs, or payment
details.

Update pinned dependencies deliberately: review upstream security advisories,
upgrade in a branch, run `.\scripts\run-tests.ps1` on Windows and the Linux
production build/checks in CI, then deploy a tested artifact. Store and retain
the lockfiles and release identifier with each deployment.

## Pre-launch checklist

- [ ] Production secrets are unique, strong, private, and not in source control.
- [ ] `SMARTERP_ENV=production`, `DEBUG=False`, explicit `ALLOWED_HOSTS`, and
  exact CORS origins are set.
- [ ] HTTPS redirect, trusted-proxy settings, secure cookies, HSTS, and
  security headers are verified through the public TLS endpoint.
- [ ] Password-reset email provider and delivery/reuse/expiry tests are
  configured; reset tokens are never exposed in production logs.
- [ ] Gunicorn/Waitress runs under a service supervisor; Django `runserver`
  and Vite dev server are not used in production.
- [ ] Frontend was built with the intended public `VITE_API_BASE_URL`; SPA
  fallback and deep-link refresh work on the deployed static host.
- [ ] MongoDB uses authentication, private networking, replica-set
  transactions, least privilege, and tested backup/restore procedures.
- [ ] Collection validators/indexes are initialized and query/transaction
  checks have passed against a dedicated staging replica set.
- [ ] Backend/frontend tests and lint/build pass; logs, monitoring, alerts,
  error tracking, retention, and incident ownership are configured.
