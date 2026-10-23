# FS Switch

**A FreeSWITCH control plane for Frappe.**

FS Switch is an open-source Frappe app and Vue 3 console for managing a
FreeSWITCH deployment: extensions, gateways, call-center queues, dialplans,
live channels, registrations and agents. Configuration lives in MariaDB and is
served to FreeSWITCH through `mod_xml_curl`; live state is read over the
FreeSWITCH Event Socket Layer (ESL).

The name is “FS Switch” — Frappe Switch.

Public repository:
<https://github.com/FarmerChazman/fs_switch>

> **Status: alpha.** The directory, dialplan compiler, ESL client, tenant-ready
> data model, cached call-setup path and console are implemented. New call flows
> use the semantic canvas with typed branch ports, live validation, route
> simulation, draft/publish/rollback, versions and a Draft-versus-Published diff.
> The original raw-application canvas remains available as an advanced escape
> hatch. Do not treat the alpha as production-ready without lab-testing it
> against your FreeSWITCH deployment.

## Why

FreeSWITCH is excellent at routing calls and awkward to administer. Most
management UIs are either a thin wrapper around XML files or a separate stack
with its own users, permissions and frontend toolchain. FS Switch keeps the
configuration in Frappe, where authentication, audit trails, permissions and
realtime events already exist.

- **One source of truth** — extensions, gateways, queues and dialplans are
  Frappe documents, not hand-edited XML.
- **No second backend** — the console uses Frappe REST, whitelisted methods and
  the existing Socket.IO/Redis realtime layer.
- **Safe defaults** — the XML-curl endpoint is protected by a shared secret and
  console editing is limited to System Managers.
- **Standalone core** — Helpdesk and CRM are optional integrations, not hard
  dependencies.

## Console

The UI follows a three-part layout:

| Area | Purpose |
|---|---|
| System tree (left) | Contexts, extensions, gateways, queues, dialplans and live views |
| Tabbed workspace | Forms, DataTables and the dialplan XML preview |
| Vue Flow canvas | Semantic call-flow editing with typed branch ports, or raw application chains |

The first release uses PrimeVue for forms and grids and Vue Flow for the
dialplan graph. See [`docs/ui.md`](docs/ui.md) for the design notes.

The product direction is in [`docs/PRODUCT.md`](docs/PRODUCT.md). The semantic
flow schema and compiler are documented in
[`docs/flow-model.md`](docs/flow-model.md).

## Documentation

- [`docs/README.md`](docs/README.md) — documentation index and operating notes
- [`docs/PRODUCT.md`](docs/PRODUCT.md) — product direction and scope
- [`docs/architecture.md`](docs/architecture.md) — control-plane/data-plane design
- [`docs/flow-model.md`](docs/flow-model.md) — Flow schema, compiler, simulator, publish and diff
- [`docs/ui.md`](docs/ui.md) — console layout and editor behaviour
- [`docs/operations.md`](docs/operations.md) — publishing, cache, ESL listener, troubleshooting and backup
- [`docs/development.md`](docs/development.md) — bench setup, tests, frontend build and releasing
- [`docs/DEFERRED.md`](docs/DEFERRED.md) — limitations and next slices
- [`SECURITY.md`](SECURITY.md) — vulnerability reporting and deployment checklist

## Architecture

```text
Browser (Vue 3 + PrimeVue + Vue Flow)
        │  REST + Frappe realtime
        ▼
Frappe / FS Switch app (Python)
        │  mod_xml_curl (directory, dialplan, callcenter.conf)
        │  ESL (commands + event stream)
        ▼
FreeSWITCH 1.10
```

More detail: [`docs/architecture.md`](docs/architecture.md).

## Quick start (Docker)

Requirements: Docker Desktop with Compose v2. The first build compiles
FreeSWITCH from source and can take 30–60 minutes.

```bash
cp .env.example .env
# edit .env and set every CHANGE_ME value
docker compose up -d --build
```

Then open <http://fs-switch.localhost:8000/fs-switch> and log in as
`Administrator` with the password from `.env`.

The first Frappe start creates the site, installs the app, builds the console
and writes the FreeSWITCH connection settings. FreeSWITCH waits for Frappe to be
healthy before it starts, so `callcenter.conf` is available through XML-curl on
the first boot.

Local values:

```dotenv
FS_SWITCH_SITE=fs-switch.localhost
FS_SWITCH_WEBRTC_URL=ws://localhost:5066
FS_SWITCH_SIP_DOMAIN=localhost
FS_SWITCH_PUBLIC_IP=127.0.0.1
FS_SWITCH_MAIN_DID=1000
```

Use `ws://` locally: the container creates a self-signed certificate that a
browser will not trust for `wss://`.

## Running on an existing bench

```bash
bench get-app https://github.com/FarmerChazman/fs_switch.git
bench --site your.site install-app fs_switch
bench --site your.site migrate
```

For a local checkout, use `bench get-app /path/to/fs_switch` instead.

Build the console:

```bash
cd apps/fs_switch/frontend
npm ci
npm run build
```

The build writes to `apps/fs_switch/fs_switch/public/console`. The console is
then available at `/fs-switch`.

### Upgrading from the initial alpha

Run `bench --site your.site migrate`. This adds the Draft/Published fields, the
version history table and the tenant fields, creates the default Tenant, then
publishes every existing valid Flow once. Existing Flows are backfilled to the
default Tenant; a Flow that fails validation stays Draft and is not served until
it is fixed and published.

Published XML and version history are server-managed. A normal save cannot
change them; only Publish and Rollback do.

## Configuration

1. Open **FS Switch Settings** in Desk (or the console Settings page).
2. Set the SIP domain, WebRTC URL, public IP, main DID and XML-curl secret.
3. Point FreeSWITCH at
   `https://<site>/api/method/fs_switch.api.xml_curl?secret=<secret>` for the
   `directory`, `configuration` and `dialplan` bindings.
4. Add an **FS Gateway** for your carrier, an **FS Extension** per user, and an
   **FS Queue** for each ring group.
5. Create an **FS Dialplan**, build the call flow in the visual editor and
   publish it.

The container entrypoint writes the matching FreeSWITCH settings from `.env`.
On a manual install, keep the Frappe settings and `xml_curl.conf.xml` in sync.

## Dialplan model

An `FS Dialplan` stores a JSON graph:

```json
{
  "nodes": [
    {
      "id": "answer",
      "type": "fs-node",
      "position": { "x": 80, "y": 80 },
      "data": {
        "label": "Answer",
        "application": "answer",
        "data": ""
      }
    },
    {
      "id": "menu",
      "type": "fs-node",
      "position": { "x": 80, "y": 220 },
      "data": {
        "label": "Play greeting",
        "application": "playback",
        "data": "ivr/ivr-welcome_to_freeswitch.wav"
      }
    }
  ],
  "edges": [{ "id": "e1", "source": "answer", "target": "menu" }]
}
```

This is the `raw` graph format. The backend topologically sorts the nodes and
compiles them into a FreeSWITCH extension. A node with
`application: "callcenter"` and `data: "support@default"` sends the caller to a
queue.

The `semantic` graph format stores intent-level nodes (`menu`, `time`,
`ring_group`, `queue`, ...) and compiles them into a deterministic state machine
with branch selectors. The console creates semantic flows by default; the
palette, typed output ports, property drawer, live validation, route simulator
and XML preview are all driven by the same node registry and compiler. See
[`docs/flow-model.md`](docs/flow-model.md) for the stored schema and generated
XML.

The route simulator walks the Draft graph, never the XML. Give it a destination,
time and caller digits and it returns the steps taken, the port chosen at each
step and the terminal step. It is a pre-publish check: it does not publish,
invalidate the cache or call FreeSWITCH.

The saved graph is a **Draft**. Publishing compiles it, stores an immutable
version, and updates the **Published** pointer. XML-curl serves only Published
XML, so a draft edit never reaches FreeSWITCH until it is published. Rollback
repoints the Published pointer to an earlier version; the Draft is left intact.

Before publishing, the **Draft vs Published** diff shows settings, entry, step
and connection changes, plus a unified XML diff. It ignores canvas positions and
edge ids, so only routing changes appear. It is read-only and available from the
Dialplans list and the semantic editor toolbar. The editor compares the saved
Draft, so save first to include canvas edits.

Flows, extensions, queues and gateways carry a Tenant. The default Tenant is
created on install and upgrade, and every call-setup document is filtered by
tenant. A document's Tenant is fixed after creation. The served dialplan uses
`published_tenant`, not the Draft tenant. The alpha resolves every domain and
context to `default`; domain/context mapping and the tenant selector are a later
slice.

The directory, dialplan and `callcenter.conf` handlers answer from a Redis
cache keyed by tenant and context. The cache is invalidated after commit when a
Flow is published, rolled back, enabled or disabled, or when settings,
extensions or queues change. Each entry keeps a last-known-good copy, so a
database or compiler failure still serves the most recent good XML. With no
last-known-good the handler returns FreeSWITCH's not-found document.

## Security

- The XML-curl endpoint is guest-accessible by design, but every request must
  present the shared secret; compare it in constant time.
- Console API methods require the `System Manager` role. The read-only flow
  catalog, validation and route simulator helpers are available to any
  authenticated user so a non-editor can still inspect a flow.
- Published XML, `published_*` fields and version history are server-managed.
  Only Publish and Rollback change what FreeSWITCH is served.
- SIP passwords and the ESL password are stored as Frappe password fields and
  are not returned in list views.
- The ESL port is not published by the Docker compose file.
- Do not expose the console or XML-curl endpoint over plain HTTP. Put the site
  behind HTTPS and use `wss://` for browser softphones.

See [`SECURITY.md`](SECURITY.md) for reporting a vulnerability.

## Repository layout

```text
apps/fs_switch/             Frappe app: DocTypes, XML-curl, ESL, console page
apps/fs_switch/frontend/    Vue 3 + PrimeVue + Vue Flow console
docker/                     Frappe and FreeSWITCH container glue
freeswitch/                 FreeSWITCH build/config templates
docs/                       Product, architecture, Flow, UI and development docs
tests/                      Python unit tests for the compiler and control plane
```

## Roadmap

- Tenant UI, domain/context mapping and tenant-scoped roles
- Console subscription to the ESL realtime event stream, with polling as fallback
- Call logs, voicemail and missed-call records
- Embedded softphone, presence and screen pop
- Carrier templates, failover and LCR/rate decks
- Media library, TTS/ASR and AI-agent nodes
- Role-based console access (agent, supervisor, administrator)
- Import/export of dialplan graphs

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for setup, tests and pull-request
expectations. Report vulnerabilities through the private advisory link in
[`SECURITY.md`](SECURITY.md), not a public issue.

## License

AGPL-3.0. See [`LICENSE`](LICENSE).

FS Switch is an independent project. It is not affiliated with or endorsed by
the FreeSWITCH or Frappe projects.
