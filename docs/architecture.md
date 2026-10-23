# Architecture

FS Switch keeps FreeSWITCH configuration in Frappe and uses FreeSWITCH as the
media/routing engine. There is no second database and no second authentication
system.

```text
┌─────────────────────────────────────────────────────────────┐
│ Browser: Vue 3 + PrimeVue + Vue Flow                        │
│  - system tree, tabbed forms, DataTables, flow canvas       │
└───────────────┬───────────────────────────────┬─────────────┘
                │ REST / whitelisted methods    │ Socket.IO
                ▼                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Frappe v16                                                   │
│  FS Switch app                                               │
│   ├─ DocTypes: Settings, Extension, Gateway, Queue, Dialplan │
│   ├─ XML-curl: directory / dialplan / callcenter.conf         │
│   ├─ ESL client: api + command whitelist                     │
│   └─ ESL listener: events → frappe.publish_realtime          │
│  MariaDB + Redis                                             │
└───────────────┬───────────────────────────────▲─────────────┘
                │ HTTP POST (mod_xml_curl)       │ ESL
                ▼                               │
┌─────────────────────────────────────────────────────────────┐
│ FreeSWITCH 1.10                                              │
│  mod_sofia, mod_callcenter, mod_xml_curl, mod_event_socket   │
└─────────────────────────────────────────────────────────────┘
```

## Configuration path

1. An administrator edits a document in the console.
2. Frappe stores it in MariaDB with the normal audit fields.
3. Publishing compiles the Flow, stores the published version and invalidates
   the call-setup cache.
4. FreeSWITCH asks the XML-curl endpoint for the directory, dialplan or
   `callcenter.conf`. The handler answers from Redis, not from a compile.
5. `reloadxml` (or a new call) picks up the change.

The XML-curl endpoint is a guest endpoint because FreeSWITCH cannot log in to
Frappe. Every request carries a shared secret in the query string; the app
compares it in constant time and rejects missing or wrong secrets before any
tenant or document lookup.

## Call-setup path

FreeSWITCH blocks on the directory, dialplan and `callcenter.conf` handlers
while routing a call, so a slow handler drops calls. `call_setup.py` caches the
whole compiled document in Redis under a key that carries the tenant and the
routing label (domain or context). A cache hit performs no database query and
no compilation.

The shared-secret hash is cached in Redis as well. With the cache warm,
FreeSWITCH can authenticate and receive last-known-good XML while MariaDB is
down. If neither Redis nor MariaDB can provide the hash, the handler fails
closed.

Each cached document also has a **Last-known-good** entry. Invalidation removes
only the current entry; last-known-good survives so a database or compiler
failure serves the most recent document that built successfully. The
`callcenter.conf` request is global in FreeSWITCH; without a context it serves
the default Tenant, which is a known multi-Tenant limitation. With no
last-known-good the handler returns FreeSWITCH's not-found document instead of
an empty one. Handlers never write and never invalidate; the control plane
invalidates after commit from publish, rollback, enable/disable, settings and
the extension/queue documents that feed the handlers.

The cache key includes a tenant. `resolve_tenant()` reads a cached routing map
of enabled Tenants: a SIP domain or a context resolves to its Tenant. If both
labels are supplied and disagree, the context wins. An unknown label falls back
to the configured default Tenant, so an existing single-Tenant deployment keeps
working without a map entry. The decision and failure modes are recorded in
[ADR 0003](adr/0003-call-setup-path-cache.md).

## Live path

- The ESL client opens a short-lived connection for commands (`show channels`,
  `uuid_kill`, `callcenter_config ...`).
- The long-running listener opens a persistent connection and subscribes to
  channel, call-center and registration events.
- Each event is annotated with the resolved Tenant and published on Frappe
  realtime as `fs_switch_call`, `fs_switch_agent` or `fs_switch_registration`.
  Recipients are limited to that Tenant's Admins and Supervisors plus System
  Managers, so an Agent never receives another extension's live rows.
- The console connects to the site's Socket.IO namespace, takes one snapshot,
  then applies events in place. While the socket is disconnected it polls the
  snapshot endpoint every 30 seconds; a reconnect takes a fresh snapshot.
- Live commands still go over a short-lived ESL connection. The API checks the
  caller's Tenant role and the target channel or agent before running a
  command.

## Why the dialplan is a graph

FreeSWITCH dialplans are nested XML. A graph is a better editing model for
humans, and the same JSON can drive three views:

- a table of ordered actions,
- a visual flow canvas,
- an XML preview.

There are two graph formats:

- `raw` - the original linear chain of FreeSWITCH applications, available in
  the advanced editor and kept as an escape hatch;
- `semantic` - intent-level nodes (`menu`, `time`, `queue`, `ring_group`, ...)
  compiled into a deterministic state machine of named extensions.

The semantic compiler is documented in
[`flow-model.md`](flow-model.md), with the decision record in
[`adr/0002-semantic-flow-graph.md`](adr/0002-semantic-flow-graph.md). The console
routes semantic documents to `SemanticFlowEditor.vue`, which edits the semantic
graph with typed ports, previews the compiled XML and can simulate a call
through the Draft graph before publishing. Raw documents keep the original
application-chain canvas.

The graph is a Draft. Publishing compiles it and stores an immutable published
version. XML-curl serves only the Published XML, so a saved draft edit cannot
change live routing until an administrator publishes it. Rollback moves the
Published pointer to an earlier version without overwriting the Draft. A
Draft-versus-Published diff compares graph identity and the compiled XML before
publish; it is read-only.

Tenant scope is carried on Flows, extensions, queues and gateways. The default
Tenant is created on install and upgrade. A document's Tenant is fixed after
creation. The directory, dialplan and callcenter documents are filtered by
tenant; the served dialplan uses `published_tenant`, not the Draft tenant. A
Flow's context must match its Tenant's default context.

Membership is a child table on `FS Tenant`. Frappe roles are global, so a
membership role projects onto `FS Switch Admin`, `FS Switch Supervisor` or
`FS Switch Agent`. DocType role permissions grant the capability and
`permission_query_conditions` plus `has_permission` hooks narrow rows to the
Tenants where the user holds that role. System Manager bypasses the narrowing.
See [`ui.md`](ui.md) for the console projection.

## App boundaries

`fs_switch` has no required apps beyond Frappe. Helpdesk, CRM and Telephony
integration is optional. This keeps the public project installable on a clean
bench and avoids coupling the console to one helpdesk vendor.

The optional Helpdesk softphone integration is documented separately. It is a
patch against Helpdesk, not a dependency of the core app.
