# FS Switch

**A FreeSWITCH control plane for Frappe.**

FS Switch is an open-source Frappe app and Vue 3 console for managing a
FreeSWITCH deployment: extensions, gateways, call-center queues, dialplans,
live channels, registrations and agents. Configuration lives in MariaDB and is
served to FreeSWITCH through `mod_xml_curl`; live state is read over the
FreeSWITCH Event Socket Layer (ESL).

The name is “FS Switch” — Frappe Switch.

> **Status: alpha.** The core directory, dialplan compiler, ESL client and
> console shell are implemented. The dialplan flow editor is intentionally
> linear in this first release; branching conditions are on the roadmap.

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
  the console is limited to System Managers.
- **Standalone core** — Helpdesk and CRM are optional integrations, not hard
  dependencies.

## Console

The UI follows a three-part layout:

| Area | Purpose |
|---|---|
| System tree (left) | Contexts, extensions, gateways, queues, dialplans and live views |
| Tabbed workspace | Forms, DataTables and the dialplan XML preview |
| Vue Flow canvas | Visual, node-based dialplan editing with a PrimeVue property drawer |

The first release uses PrimeVue for forms and grids and Vue Flow for the
dialplan graph. See [`docs/ui.md`](docs/ui.md) for the design notes.

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
bench get-app /path/to/fs_switch
bench --site your.site install-app fs_switch
bench --site your.site migrate
```

Build the console:

```bash
cd apps/fs_switch/frontend
yarn install
yarn build
```

The build writes to `apps/fs_switch/fs_switch/public/console`. The console is
then available at `/fs-switch`.

## Configuration

1. Open **FS Switch Settings** in Desk (or the console Settings page).
2. Set the SIP domain, WebRTC URL, public IP, main DID and XML-curl secret.
3. Point FreeSWITCH at
   `https://<site>/api/method/fs_switch.api.xml_curl?secret=<secret>` for the
   `directory`, `configuration` and `dialplan` bindings.
4. Add an **FS Gateway** for your carrier, an **FS Extension** per user, and an
   **FS Queue** for each ring group.
5. Create an **FS Dialplan** and build the call flow in the visual editor.

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

The backend topologically sorts the nodes and compiles them into a FreeSWITCH
extension. A node with `application: "callcenter"` and
`data: "support@default"` sends the caller to a queue. The XML preview in the
console is generated by the same compiler.

## Security

- The XML-curl endpoint is guest-accessible by design, but every request must
  present the shared secret; compare it in constant time.
- Console API methods require the `System Manager` role.
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
docs/                       Architecture, UI notes and development guide
tests/                      Small Python and frontend checks
```

## Roadmap

- Branching dialplan conditions and IVR digit routing in the flow editor
- Call logs, voicemail and missed-call records
- Real-time channel/agent grids driven by the ESL event stream
- Optional Helpdesk softphone integration
- Role-based console access (agent, supervisor, administrator)
- Import/export of dialplan graphs

## License

AGPL-3.0. See [`LICENSE`](LICENSE).

FS Switch is an independent project. It is not affiliated with or endorsed by
the FreeSWITCH or Frappe projects.
