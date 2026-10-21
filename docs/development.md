# Development

## Prerequisites

- Python 3.10+ (Frappe v16 bench uses 3.14 in the Docker image)
- Node 20+ and Yarn 1.22
- MariaDB and Redis for a local bench
- Docker Desktop if you want the container path

## Backend

The app is a normal Frappe app. To install it on a bench:

```bash
bench get-app /path/to/fs_switch
bench --site dev.localhost install-app fs_switch
bench --site dev.localhost migrate
```

Useful commands:

```bash
bench --site dev.localhost console
bench --site dev.localhost execute fs_switch.api.get_bootstrap
bench --site dev.localhost execute fs_switch.api.get_live_data
```

The XML-curl endpoint can be checked without FreeSWITCH once the secret is set:

```bash
curl 'http://dev.localhost:8000/api/method/fs_switch.api.xml_curl?secret=...&section=dialplan'
```

## Frontend

```bash
cd apps/fs_switch/frontend
yarn install
yarn dev        # Vite dev server
yarn build      # writes ../fs_switch/public/console
```

The Vite config sets `base` to `/assets/fs_switch/console/` and emits stable
asset names (`app.js`, `app.css`) so `www/fs-switch.html` can load them without
a manifest lookup.

## Tests

```bash
python -m compileall apps/fs_switch
python -m pytest tests
```

The dialplan compiler test does not need a Frappe site.

## Docker

```bash
cp .env.example .env
# edit secrets
docker compose up -d --build
docker compose logs -f frappe
```

The FreeSWITCH image compiles FreeSWITCH from source. Rebuilds are cached; the
first build is the slow one.

## FreeSWITCH config

The container entrypoint writes:

- `xml_curl.conf.xml` with the Frappe URL and secret,
- `webrtc.xml` for browser softphones,
- `event_socket.conf.xml` with the ESL password,
- `vars.xml` with the public IP,
- a self-signed TLS certificate when no certificate is mounted.

For a production host, use `freeswitch/install/install-config.sh` and a real
TLS certificate in `/etc/freeswitch/tls/wss.pem`.

## Releasing

1. Update `CHANGELOG.md` and the app version in `pyproject.toml`.
2. Run the checks and a clean Docker build.
3. Tag the commit and publish a GitHub release with the source archive.
4. Keep the AGPL license and copyright notices intact.
