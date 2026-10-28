# Local MongoDB setup on Windows

This guide configures MongoDB Community Server as a Windows service and a
single-node replica set for local SmartERP development. Run service, config,
and file-permission commands in an elevated PowerShell window when indicated.
Keep MongoDB bound to localhost; this setup is not intended to expose MongoDB
to a network.

## Install the Windows tools

Download the Windows x64 versions from MongoDB's official download pages:

1. [MongoDB Community Server](https://www.mongodb.com/try/download/community):
   choose the Windows MSI installer. In setup, choose **Complete** and install
   MongoDB as a Windows service. The default service name is `MongoDB`.
2. [MongoDB Shell (`mongosh`)](https://www.mongodb.com/try/download/shell):
   download and install the Windows MSI separately if it was not included with
   your Server installation.
3. [MongoDB Compass](https://www.mongodb.com/try/download/compass): download and
   install the Windows version. Compass is a graphical client; it is optional
   for running the backend.
4. [MongoDB Database Tools](https://www.mongodb.com/try/download/database-tools):
   download and install the Windows ZIP or MSI separately. This package
   includes `mongodump` and `mongorestore`; they are not the Community Server.
   Add the tools' `bin` folder to PATH if the installer did not do that.

Open a new PowerShell window after installation so PATH changes are loaded.
Check that each executable is available:

```powershell
mongod --version
mongosh --version
mongodump --version
```

Each command should print its tool's version and exit successfully. If
PowerShell says a command is not recognized, check that component's install
folder is on PATH, then open a fresh PowerShell window.

## Configure a single-node replica set

Do these steps in order. MongoDB must start with replica-set mode enabled
before the replica set can be initialized. Initialize it before adding users
and enabling access control. Finally, provide the key file before enabling
authorization: an authenticated replica-set member requires a key file to
authenticate its internal replication connections.

### A. Stop the service and enable replica-set mode

Open **PowerShell as Administrator**. Find the installed server version's
`bin` folder; the default config is commonly:

```text
C:\Program Files\MongoDB\Server\<version>\bin\mongod.cfg
```

Stop the service:

```powershell
Stop-Service MongoDB
```

Open `mongod.cfg` in an Administrator editor, for example:

```powershell
notepad.exe "C:\Program Files\MongoDB\Server\<version>\bin\mongod.cfg"
```

Keep the loopback-only bind address and add the `replication` section. Preserve
other existing settings such as `storage` and `systemLog`.

```yaml
net:
  bindIp: 127.0.0.1
  port: 27017

replication:
  replSetName: rs0
```

Save the file and start the service:

```powershell
Start-Service MongoDB
Get-Service MongoDB
```

### B. Initialize the replica set and confirm PRIMARY

Connect locally:

```powershell
mongosh "mongodb://localhost:27017"
```

At the `mongosh` prompt, run the requested configuration exactly:

```javascript
rs.initiate({_id: "rs0", members: [{_id: 0, host: "localhost:27017"}]})
rs.status()
```

Wait a few seconds and run `rs.status()` again if the member is still
`STARTUP` or `STARTUP2`. Initialization succeeds when the `rs.status()` output
shows the member state `PRIMARY` (state number `1`). The explicit
`localhost:27017` host is intentional: it is the name the local driver can
resolve consistently. Do not initialize this same data directory with a
different replica-set name.

### C. Create the administrator and scoped application users

While access control is not enabled yet, run these commands at the `mongosh`
prompt. `passwordPrompt()` prompts without putting a password in shell history.

Create the administrator on the `admin` database:

```javascript
use admin
db.createUser({
  user: "smarterp_admin",
  pwd: passwordPrompt(),
  roles: [{role: "root", db: "admin"}]
})
```

Create an application user limited to the SmartERP database:

```javascript
use smarterp
db.createUser({
  user: "smarterp_app",
  pwd: passwordPrompt(),
  roles: [{role: "readWrite", db: "smarterp"}]
})
```

Create a separate user limited to the test database:

```javascript
use smarterp_test
db.createUser({
  user: "smarterp_test_user",
  pwd: passwordPrompt(),
  roles: [{role: "readWrite", db: "smarterp_test"}]
})
```

Save the passwords in an appropriate local secret store. Do not put real
passwords in this repository. The test user must not be used by the normal
application.

### D. Create the key file, enable authorization, and verify login

In elevated PowerShell, create the key file outside the repository. This exact
command creates 756 cryptographically random bytes and writes their Base64
representation, without a newline, to `C:\data\mongo-keyfile`:

```powershell
New-Item -ItemType Directory -Force -Path 'C:\data' | Out-Null
$keyBytes = New-Object byte[] 756
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try {
    $rng.GetBytes($keyBytes)
    [System.IO.File]::WriteAllText(
        'C:\data\mongo-keyfile',
        [Convert]::ToBase64String($keyBytes),
        [System.Text.Encoding]::ASCII
    )
}
finally {
    $rng.Dispose()
}
```

The Windows service account must be able to read the key file. Check the
service's configured identity:

```powershell
Get-CimInstance Win32_Service -Filter "Name='MongoDB'" | Select-Object Name, StartName
```

The MSI commonly runs the service as Network Service. For that default
identity, restrict inherited access and grant its well-known Windows SID read
access (and Administrators full control):

```powershell
icacls 'C:\data\mongo-keyfile' /inheritance:r /grant:r '*S-1-5-20:(R)' 'BUILTIN\Administrators:(F)'
```

If `StartName` shows a different service account, grant read permission to
that account instead. Keep the key file outside the repository and do not
share it between unrelated deployments.

Stop the service, open the same `mongod.cfg` as Administrator, and add the
security settings alongside the existing `net` and `replication` settings:

```yaml
security:
  keyFile: C:\data\mongo-keyfile
  authorization: enabled
```

MongoDB **requires** a key file when authorization is enabled on a replica-set
member. Without it, `mongod` refuses to start. Restart and check the service:

```powershell
Restart-Service MongoDB
Get-Service MongoDB
```

Test an authenticated administrator login (the `--password` option prompts
for the password):

```powershell
mongosh "mongodb://localhost:27017/admin?replicaSet=rs0" --username smarterp_admin --authenticationDatabase admin --password
```

Test the application user's scoped database login:

```powershell
mongosh "mongodb://localhost:27017/smarterp?replicaSet=rs0&authSource=smarterp" --username smarterp_app --authenticationDatabase smarterp --password
```

The first prompt should authenticate to `admin`; the second should authenticate
to `smarterp`. A successful shell connection does not grant either application
user access to other databases.

## Connection URI for the backend

The application URI has this shape:

```text
mongodb://smarterp_app:<URL_ENCODED_PASSWORD>@localhost:27017/smarterp?replicaSet=rs0&authSource=smarterp
```

URL-encode reserved characters in the password (for example `@`, `:`, `/`, `?`,
`#`, and `%`). Put the real value only in a local, ignored `backend/.env`; never
commit that file. The tracked [`backend/.env.example`](../backend/.env.example)
contains a placeholder, not a usable password. The backend must read
`MONGO_URI` and connect with PyMongo; do not put MongoDB credentials in the
frontend environment.

## Start, stop, and check the service

Run these commands in PowerShell; use an elevated window if Windows reports
that permission is required:

```powershell
Start-Service MongoDB
Stop-Service MongoDB
Get-Service MongoDB
```

`Get-Service` should report `Running` after startup and `Stopped` after stopping.

## Back up and restore

These commands prompt for the application user's password rather than putting
it in shell history. They save and restore the `smarterp` database only; they
do not back up MongoDB configuration, the key file, or other databases.

```powershell
mongodump --uri "mongodb://localhost:27017/smarterp?replicaSet=rs0&authSource=smarterp" --username smarterp_app --authenticationDatabase smarterp --password --out "C:\backups\smarterp"
```

Restore that dump into the same database, replacing matching collections:

```powershell
mongorestore --uri "mongodb://localhost:27017/smarterp?replicaSet=rs0&authSource=smarterp" --username smarterp_app --authenticationDatabase smarterp --password --drop --dir "C:\backups\smarterp"
```

Keep backups outside the repository, protect their access, and periodically
test restoring into a disposable database before relying on them.

## What the replica set changes

A replica set is a group of MongoDB servers that maintain the same data and
elect one server as the **primary**, which accepts writes. This local setup has
only one member: it provides replica-set features but **not** a spare server or
high availability. `localhost:27017` is the only network address configured
here.

MongoDB multi-document transactions need a replica set (or a sharded cluster)
because the server coordinates transactional changes through that deployment
mode. A standalone server does not support these transactions. This matters
for SmartERP operations that must update related records together, such as
receiving a purchase order and recording its stock movement.

Keep transactions short. They add coordination and resource overhead, and
MongoDB limits their lifetime (60 seconds by default). Do not wait for user
input, make network calls, or perform long work inside a transaction. Create
the collections and indexes before using them in a transaction; do not rely on
implicit collection creation inside a transaction.

### Deployment choices

| Choice | What it is | Trade-off |
| --- | --- | --- |
| Standalone | One MongoDB server without replica-set mode | Simplest for basic local experiments, but does not support the multi-document transactions SmartERP needs. |
| Single-node replica set | One server configured as a replica set | Supports transaction development locally, but has no redundancy or failover to another server. |
| MongoDB Atlas | MongoDB's hosted database service | Avoids managing the local database server and can provide managed deployment options. Pricing and free-tier availability depend on current plans and region; check Atlas pricing rather than assuming it is free. |

## How application data flows

```text
React frontend
    -> HTTP request to Django REST Framework backend
    -> backend serializer validates input
    -> service applies business rules
    -> repository uses PyMongo and MONGO_URI
    -> MongoDB database
    -> result returns through backend response to the frontend
```

The frontend must never connect directly to MongoDB. The backend owns database
credentials and validates requests before a repository makes database calls.

## Common mistakes and debugging

- **A command is not recognized:** install that separate component, add its
  `bin` folder to PATH, and reopen PowerShell.
- **The service does not start after editing config:** check YAML indentation,
  the config path, the key-file path/permissions, and the MongoDB log. The
  default log is commonly under `C:\Program Files\MongoDB\Server\<version>\log`.
  A replica-set member with authorization enabled but no readable key file
  will not start.
- **`rs.status()` says not initialized or no primary:** check that the config
  contains `replication.replSetName: rs0`, the service is running, and
  `rs.initiate()` used the same set name. Allow a short election delay, then
  check again.
- **Authentication fails:** check the username's database, the `authSource`
  value, the password, and percent-encoding of reserved password characters.
  The admin user authenticates against `admin`; `smarterp_app` authenticates
  against `smarterp`.
- **PyMongo reports that transactions require a replica set:** verify
  `rs.status()` reports a `PRIMARY`, and that the URI includes
  `replicaSet=rs0`. Confirm the backend loaded the intended `.env`.
- **Transactions fail when accessing a collection:** create required
  collections and indexes before starting the transaction.
- **The backend cannot connect:** confirm `Get-Service MongoDB` reports
  `Running`, `bindIp` remains `127.0.0.1`, port 27017 is available, and no
  real secret was copied with literal angle brackets from the example URI.
