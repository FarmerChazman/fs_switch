# Development

## Prerequisites

- Python 3.10+ (the Docker image uses the Python version shipped with Frappe
  v16)
- Node 20+ and npm (the frontend has a `package-lock.json`)
- MariaDB and Redis for a local bench
- FreeSWITCH 1.10 for end-to-end call testing
- Docker Desktop if you want the container path

## Backend

The app is a normal Frappe app. To install it on a bench:

```bash
bench get-app https://github.com/FarmerChazman/fs_switch.git
bench --site dev.localhost install-app fs_switch
bench --site dev.localhost migrate
```

Run `migrate` after pulling changes that add DocType fields, patches or a new
schema. The migration:

- creates the configured default Tenant if it is missing,
- creates `FS Switch Admin`, `FS Switch Supervisor` and `FS Switch Agent`,
- backfills `tenant` on existing Flows, extensions, queues and gateways,
- backfills `published_tenant` on already-published Flows,
- publishes every existing valid Flow once,
- syncs projected roles from Tenant membership.

Useful commands:

```bash
bench --site dev.localhost console
bench --site dev.localhost execute fs_switch.api.get_bootstrap
bench --site dev.localhost execute fs_switch.api.get_live_data
bench --site dev.localhost execute fs_switch.setup.configure_from_env
```

The XML-curl endpoint can be checked without FreeSWITCH once the secret is set:

```bash
curl 'http://dev.localhost:8000/api/method/fs_switch.api.xml_curl?secret=...&section=dialplan'
```

### ESL listener

The listener is a long-running process. Start it next to the bench:

```bash
bench --site dev.localhost execute fs_switch.esl_listener.run
```

For production, install `freeswitch/install/esl-listener.service` and adjust the
site name and paths. The Docker entrypoint starts the listener automatically.
The listener reconnects after a FreeSWITCH restart.

The listener publishes `fs_switch_call`, `fs_switch_agent` and
`fs_switch_registration` on Frappe realtime. The console connects to
`/<site>` through `socket.io-client`. In development the Vite server proxies
`/api` and `/assets`; Socket.IO still connects to the Frappe origin. Set
`fs_switch_socketio_url` in `site_config.json` when the socket is on another
public host or port.

## Frontend

```bash
cd apps/fs_switch/frontend
npm ci
npm run dev        # Vite dev server on :5174
npm run build      # writes ../fs_switch/public/console
```

The Vite config sets `base` to `/assets/fs_switch/console/` and emits stable
asset names (`app.js`, `app.css`) so `www/fs-switch.html` can load them without a
manifest lookup. The dev server proxies `/api` and `/assets` to
`http://fs-switch.localhost:8000`.

## Tests

```bash
python -m compileall apps/fs_switch tests
python -m unittest discover -s tests -v
git diff --check
```

`pytest tests` is also supported. The compiler, publish, call-setup, route
simulator, diff, Tenant mapping and ESL listener tests run without a Frappe
site. DocType validation, permission hooks, patches, XML-curl handlers,
Socket.IO authentication and the console need a live bench for end-to-end
verification.

The frontend build is the frontend check:

```bash
cd apps/fs_switch/frontend
npm run build
```

## Docker

```bash
cp .env.example .env
# edit every CHANGE_ME value
docker compose up -d --build
docker compose logs -f frappe
```

The FreeSWITCH image compiles FreeSWITCH from source. Rebuilds are cached; the
first build is the slow one. The compose file publishes the console on port 8000
and Socket.IO on port 9000. It does not publish the ESL port.

## FreeSWITCH config

The container entrypoint writes:

- `xml_curl.conf.xml` with the Frappe URL and secret,
- `webrtc.xml` for browser softphones,
- `event_socket.conf.xml` with the ESL password,
- `vars.xml` with the public IP,
- a self-signed TLS certificate when no certificate is mounted.

For a production host, use `freeswitch/install/install-config.sh` and a real TLS
certificate in `/etc/freeswitch/tls/wss.pem`.

## Call-setup cache

The directory, dialplan and `callcenter.conf` handlers serve whole documents from
Redis. Keys carry the Tenant and routing label:

```text
fs_switch:xml:current:<kind>:<tenant>:<name>
fs_switch:xml:last-known-good:<kind>:<tenant>:<name>
```

Publish, rollback, enable/disable, settings, Tenant, extension, queue and
gateway changes invalidate the current key after commit. Handlers never
invalidate. Last-known-good has no expiry and is not overwritten by an empty
build. If no last-known-good exists, the handler returns FreeSWITCH's not-found
document.

The served dialplan is filtered by `published_tenant`, not the Draft tenant. A
normal save cannot change `published_*` fields or version history; only publish
and rollback do.

## Documentation

- [`README.md`](../README.md) - install, configuration and feature overview
- [`docs/README.md`](README.md) - documentation index
- [`PRODUCT.md`](PRODUCT.md) - product direction and scope
- [`architecture.md`](architecture.md) - control-plane and data-plane design
- [`flow-model.md`](flow-model.md) - Flow schema, compiler, simulator, publish and diff
- [`ui.md`](ui.md) - console layout and editor behaviour
- [`operations.md`](operations.md) - publishing, cache, ESL listener, troubleshooting and backup
- [`DEFERRED.md`](DEFERRED.md) - limitations and next slices
- [`adr/`](adr) - architecture decision records

## Releasing

1. Update `CHANGELOG.md` and the app version in `pyproject.toml`.
2. Run the checks and a clean Docker build.
3. Build the frontend with `npm run build`.
4. Tag the commit and publish a GitHub release with the source archive.
5. Keep the AGPL license and copyright notices intact.
