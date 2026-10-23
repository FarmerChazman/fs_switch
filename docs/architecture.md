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
failure serves the most recent document that built successfully. With no
last-known-good the handler returns FreeSWITCH's not-found document instead of
an empty one. Handlers never write and never invalidate; the control plane
invalidates after commit from publish, rollback, enable/disable, settings and
the extension/queue documents that feed the handlers.

The cache key includes a tenant. The single-tenant alpha has an FS Tenant
DocType, a default Tenant and tenant-scoped documents; `resolve_tenant()` caches
the configured default in Redis and still resolves every domain/context to it.
Domain/context mapping changes the resolver, not the handler or cache shape. The
decision and failure modes are recorded in
[ADR 0003](adr/0003-call-setup-path-cache.md).

## Live path

- The ESL client opens a short-lived connection for commands (`show channels`,
  `uuid_kill`, `callcenter_config ...`).
- The long-running listener opens a persistent connection and subscribes to
  channel and call-center events.
- Events are published on Frappe's realtime channel. The first release polls the
  live endpoint every few seconds; subscribing the console to the socket stream
  is deferred.

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
tenant; the served dialplan uses `published_tenant`, not the Draft tenant. The
alpha resolves every domain and context to `default`.

## App boundaries

`fs_switch` has no required apps beyond Frappe. Helpdesk, CRM and Telephony
integration is optional. This keeps the public project installable on a clean
bench and avoids coupling the console to one helpdesk vendor.

The optional Helpdesk softphone integration is documented separately. It is a
patch against Helpdesk, not a dependency of the core app.
