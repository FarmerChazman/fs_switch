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
3. FreeSWITCH asks the XML-curl endpoint for the directory, dialplan or
   `callcenter.conf`.
4. The app renders XML from the current documents and returns it.
5. `reloadxml` (or a new call) picks up the change.

The XML-curl endpoint is a guest endpoint because FreeSWITCH cannot log in to
Frappe. Every request carries a shared secret in the query string; the app
compares it in constant time and rejects missing or wrong secrets.

## Live path

- The ESL client opens a short-lived connection for commands (`show channels`,
  `uuid_kill`, `callcenter_config ...`).
- The long-running listener opens a persistent connection and subscribes to
  channel and call-center events.
- Events are published on Frappe's realtime channel. The console can subscribe
  to them; the first release also polls the live endpoint every few seconds so
  it works without a socket connection.

## Why the dialplan is a graph

FreeSWITCH dialplans are nested XML. A graph is a better editing model for
humans, and the same JSON can drive three views:

- a table of ordered actions,
- a visual flow canvas,
- an XML preview.

The compiler topologically sorts the graph and emits a single
`<extension><condition>...` block. The first release supports linear flows;
branching conditions are deliberately deferred until the model can represent
them without losing round-trip fidelity.

## App boundaries

`fs_switch` has no required apps beyond Frappe. Helpdesk, CRM and Telephony
integration is optional. This keeps the public project installable on a clean
bench and avoids coupling the console to one helpdesk vendor.

The optional Helpdesk softphone integration is documented separately. It is a
patch against Helpdesk, not a dependency of the core app.
