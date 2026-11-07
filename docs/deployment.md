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
| `JWT_ISSUER`, `JWT_AUDIENCE` | Development defaults | Set stable values for this deployment; tokens must use matching values |
| `JWT_ACCESS_TOKEN_LIFETIME_SECONDS`, `JWT_REFRESH_TOKEN_LIFETIME_SECONDS` | Development defaults | Review against the security and reauthentication policy |
| `CORS_ALLOWED_ORIGINS` | Exact local frontend origin | Exact HTTPS frontend origins; no wildcard |
| `REFRESH_COOKIE_NAME`, `REFRESH_COOKIE_PATH` | Development defaults | Keep the path as narrow as the refresh routes permit |
| `REFRESH_COOKIE_SECURE` | May be false for local HTTP | Forced true in production |
| `REFRESH_COOKIE_HTTPONLY` | True | Keep true so browser JavaScript cannot read the refresh token |
| `REFRESH_COOKIE_SAMESITE` | `Lax` | Use `Lax` for same-site deployments; see cookie guidance below |
| `REFRESH_COOKIE_DOMAIN` | Unset | Prefer unset (host-only); set only when a reviewed design requires shared subdomains |
| `SECURE_SSL_REDIRECT` | False | Defaults to true; only disable for local plaintext smoke tests |
| `SECURE_HSTS_SECONDS` | 0 | Defaults to 31,536,000; must be positive |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD` | Development defaults | Enable only after confirming every covered hostname is HTTPS-ready |
| `TRUST_X_FORWARDED_PROTO` | False | Enable only behind a trusted TLS-terminating proxy |
| `LOG_FILE` | `backend/logs/smarterp.log` | Writable persistent protected file path |
| `LOG_MAX_BYTES`, `LOG_BACKUP_COUNT`, `LOG_LEVEL` | Defaults | Tune for host storage and retention; keep at least `INFO` in production |
| `MONGO_TEST_URI`, `MONGO_TEST_DB_NAME` | Optional dedicated test database | Test/staging only; never point tests at production |
| `VITE_API_BASE_URL` | `http://localhost:8000/api` | Frontend build-time public API URL; set before `npm run build`, never put secrets here |

Copy `backend/.env.example` to an ignored `backend/.env`. Supply real secrets
through a protected environment/secret manager or a file readable only by the
service account. Never commit `.env` or paste secret values into command lines,
tickets, or logs. MongoDB URI reserved characters in credentials must be
percent-encoded. The `MONGO_TEST_URI` must use a separate dedicated test
database/user and must never point at production.

`ALLOWED_HOSTS` is a comma-separated allowlist of hostnames from the HTTP
`Host` header, without a scheme, path, or port (for example,
`api.example.com`). Include every hostname that actually reaches Django; do
not use `*`. It is independent of `CORS_ALLOWED_ORIGINS`, which lists complete
browser origins (scheme + hostname + optional port), such as
`https://erp.example.com`. If the browser calls `https://api.example.com`,
allow `api.example.com` in `ALLOWED_HOSTS` and `https://erp.example.com` in
`CORS_ALLOWED_ORIGINS`.

### Hosting choices

These are deployment patterns, not endorsements. Compare current provider
pricing, support, data location, service limits, and recovery guarantees
before choosing; none of these options is assumed to be free.

| Component | Option | Trade-offs to evaluate |
|---|---|---|
| Frontend | Static hosting/CDN | Simple delivery of `frontend/dist/` and global caching; check custom-domain/TLS, SPA fallback, build/deploy integration, bandwidth and support costs. |
| Frontend | Same Linux VPS as the API | One host and a same-origin `/api/` route can simplify cookies and CORS; you own patching, capacity, availability, TLS, backups and recovery. |
| Frontend | PaaS static-site service | Managed builds and deploys can reduce server work; check build minutes, bandwidth, region, headers/SPA behavior, availability and pricing. |
| Backend | Linux VPS with systemd + Gunicorn | Direct control over OS, network and process; requires you to operate patching, TLS proxy, monitoring, scaling, failover and recovery. |
| Backend | PaaS application service | Managed deploys, restarts, logs and health probes may reduce operations; confirm Python/WSGI support, private outbound access to MongoDB, persistent-secret handling, worker limits, logs, regions, service limits and total cost. |
| MongoDB | MongoDB Atlas | Managed replica-set operations, backups and monitoring options; select a suitable paid/service tier and region, configure database users and private connectivity/IP access lists, and check backup, retention, egress and support costs. |
| MongoDB | Self-managed MongoDB on a private host/network | More control over topology and maintenance windows; you own replica-set operations, encryption, patching, monitoring, backup, restore drills and availability. Keep it private and do not expose its port publicly. |

You can combine providers, but verify the network path between the backend and
MongoDB before committing to the design. Keep the database on a private
connection where available; if a provider requires an IP access list, allow
only the backend's fixed egress addresses and approved administration paths.
Do not open MongoDB to `0.0.0.0/0` or otherwise expose it to the public
Internet.

### Refresh-cookie and CORS choices

The API enables credentialed CORS. Use exact origins, not `*`, and keep the
refresh cookie `HttpOnly` and `Secure` in production. Prefer serving the
frontend and API on the same origin (for example, route `/api/` through the
same proxy) or on subdomains of the same registrable domain
(`erp.example.com` and `api.example.com`). Those subdomains are cross-origin
for CORS but are generally same-site for cookie `SameSite` handling; `Lax`
is the configured default. Leave `REFRESH_COOKIE_DOMAIN` unset unless sharing
the cookie across subdomains is a documented requirement.

If frontend and API are on different registrable domains, the refresh cookie
is cross-site: it generally needs `REFRESH_COOKIE_SAMESITE=None` and
`REFRESH_COOKIE_SECURE=True`. Browser third-party-cookie restrictions can
still block it. CORS is not a CSRF defense. Do not enable this arrangement
until cookie-authenticated refresh requests have a reviewed and tested CSRF
defense; if that is not available, use a same-site domain or reverse-proxy
design instead. Keep credentialed requests enabled only where needed and
verify login, refresh, logout, and rejected-origin behavior in a real browser.

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

For Caddy, a minimal site definition can serve the built single-page app and
proxy the API. With the domain pointed at this server and inbound ports 80/443
permitted, Caddy obtains and renews publicly trusted HTTPS certificates
automatically (using Let's Encrypt when applicable):

```caddyfile
erp.example.com {
    encode zstd gzip

    handle /api/* {
        reverse_proxy 127.0.0.1:8000
    }

    handle {
        root * /srv/smarterp/frontend/dist
        try_files {path} /index.html
        file_server
    }
}
```

For nginx, install/configure Certbot for the chosen Linux distribution and
use its nginx integration (or an equivalent certificate-renewal workflow) to
obtain and renew Let's Encrypt certificates. Validate automatic renewal
before launch. In either case, allow inbound HTTP only as needed for
certificate issuance/redirects and allow HTTPS; keep Gunicorn bound to
loopback or a private socket. Never publish its application port or MongoDB's
port.

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
- Require MongoDB authentication and TLS for remote connections. Keep the
  database on a private network; bind/listen only on private interfaces and
  allow database traffic only from backend hosts and approved administrative
  networks using firewall rules or Atlas network access controls. Never
  expose MongoDB directly to the public Internet.
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
cluster URI and the `--gzip` option. Example for tools installed on the Linux
backup/operations host (substitute a private target URI and a new isolated
database name):

```bash
# The URI identifies the cluster/database; --password prompts interactively.
mongodump --uri="mongodb+srv://cluster.example.mongodb.net/smarterp?authSource=admin" \
  --username="$MONGO_BACKUP_USER" --authenticationDatabase=admin --password \
  --db=smarterp --gzip --out="/var/backups/smarterp/2026-11-07"

# Restore only into an isolated recovery-test database/cluster.
mongorestore --uri="mongodb+srv://recovery.example.mongodb.net/?authSource=admin" \
  --username="$MONGO_RESTORE_USER" --authenticationDatabase=admin --password \
  --gzip --nsFrom="smarterp.*" --nsTo="smarterp_restore_test.*" \
  --drop "/var/backups/smarterp/2026-11-07/smarterp"
```

Use secure secret handling and a backup identity with only the required
backup permissions; use a separate restore identity with the permissions
needed for the isolated target. Store encrypted backups off-host with
restricted access and documented retention. A successful dump is not proof
that a backup can be restored. On a regular schedule, restore a recent backup
to an isolated replica set/database, verify collections, validators and
indexes, check representative records, run application checks and safe
read/write workflow tests, record restore duration and outcome, and then
destroy the isolated test data using your approved procedure. Never restore
over production as a test.

The public `GET /api/health/` endpoint is a **liveness** check only: it returns
success when Django can answer and does not query MongoDB. Use it for process
and reverse-proxy availability, but separately monitor MongoDB connection
and replica-set state with a private authenticated probe or provider
monitoring. A database-backed readiness check is not implemented by this
endpoint. Monitor disk space, backup age, HTTP error/latency rates, worker
restarts, certificate renewal and log rotation; alert on repeated API errors,
database unavailability and failed/overdue backups.

Centralize service/reverse-proxy logs where appropriate, restrict access and
retention, and ensure the service account can write the configured `LOG_FILE`.
The rotating Django log defaults to 10 MiB x five files; adapt it to host
capacity and central log shipping/retention. Use an error-tracking service
only after reviewing data scrubbing, access controls and retention. Error
tracking is not configured in this repository. Do not log bearer/refresh
tokens, reset URLs, passwords, MongoDB URIs, or payment/customer details.

Review upstream security advisories continuously and schedule regular
dependency reviews. Update pinned Python dependencies in
`backend/requirements*.txt` and JavaScript dependencies through the frontend
package manifest and lockfile in a dedicated branch; prioritize actively
exploited or critical fixes, review release notes and breaking changes, then
run backend tests, frontend tests/lint/build and Linux production checks in
CI. Deploy a tested, identifiable artifact through staging with a rollback
plan. Keep lockfiles and release identifiers with each deployment; do not
silently float production dependencies.

## Pre-launch checklist

- [ ] Production secrets are unique, strong, private, and not in source control.
- [ ] `SMARTERP_ENV=production`, `DEBUG=False`, explicit `ALLOWED_HOSTS`, exact
  CORS origins, and reviewed JWT issuer/audience/lifetimes are set.
- [ ] The hosting choice, regions, network paths, capacity, provider limits,
  costs, availability commitments, data location and recovery ownership are
  understood for frontend, backend and MongoDB.
- [ ] HTTPS redirect, trusted-proxy settings, secure cookies, HSTS, and
  security headers are verified through the public TLS endpoint.
- [ ] Refresh cookie is `HttpOnly`, `Secure`, and has a deliberate `SameSite`
  and domain/path; cross-site cookie use has tested CSRF protection and
  browser compatibility.
- [ ] Password-reset email provider and delivery/reuse/expiry tests are
  configured; reset tokens are never exposed in production logs.
- [ ] Linux Gunicorn runs under systemd or the selected PaaS supervisor,
  bound privately behind the reverse proxy; Django `runserver`, Vite dev
  server and public Gunicorn/Waitress ports are not used in production.
- [ ] Reverse-proxy TLS certificate issuance and renewal are configured and
  tested; only intended public ports are reachable.
- [ ] Frontend was built with the intended public `VITE_API_BASE_URL`; SPA
  fallback and deep-link refresh work on the deployed static host.
- [ ] MongoDB authentication, TLS, least privilege, private network/firewall
  rules, replica-set transactions, and restricted administrator access are
  verified; no MongoDB port is publicly reachable.
- [ ] Collection validators/indexes are initialized and query/transaction
  checks have passed against a dedicated staging replica set.
- [ ] `init_db` completed against the intended database after index/data
  compatibility review.
- [ ] Encrypted off-host backups are scheduled, access-controlled, retained,
  and a restore test to an isolated target has passed and been recorded.
- [ ] Backend/frontend tests and lint/build pass; health/DB monitoring,
  actionable alerts, log retention, error tracking (or an explicit decision
  not to use it), and incident ownership are configured.
- [ ] Dependency-update ownership, security-advisory review, staging checks,
  release identification and rollback procedure are documented.
