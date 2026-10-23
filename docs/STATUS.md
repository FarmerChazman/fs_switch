# Implementation status

This document compares the current repository with the original source material:

- [`product-thesis.txt`](product-thesis.txt)
- [`FreeSWITCH UI.txt`](FreeSWITCH%20UI.txt)
- [`world-class FreeSWITCH UI layout idea.txt`](world-class%20FreeSWITCH%20UI%20layout%20idea.txt)

The source documents describe an earlier alpha: single-tenant, linear raw
application graphs, five-second polling and no publish pipeline. The current app
has moved beyond that snapshot. **Complete** below means implemented in the
repository and covered by unit/build checks, not accepted in a live FreeSWITCH
deployment.

## Complete

### Architecture

- Frappe remains the single backend and control plane.
- Vue 3 + PrimeVue + Vue Flow console.
- MariaDB + Redis + Socket.IO.
- `mod_xml_curl` for directory, dialplan and `callcenter.conf`.
- ESL for commands and events.
- No second backend and no second authentication system.
- Python-side validation and compilation.

### Flow model and compiler

- Semantic graph format plus the raw FreeSWITCH application escape hatch.
- Node registry: `answer`, `play`, `menu`, `time`, `ring_group`, `queue`,
  `voicemail`, `transfer`, `conference`, `park`, `set`, `sleep`, `record`,
  `hangup`.
- Typed branch ports: menu digits/timeout, time match/no-match.
- Strict validation for unknown nodes, missing routes, dangling edges,
  unreachable nodes and terminal-node edges.
- Deterministic named-extension compilation.
- Canvas, table and read-only XML projections of the same graph.
- Route simulator that walks the Draft graph.
- Draft-versus-Published graph and XML diff.

### Publishing

- Explicit Draft and Published state.
- Immutable version history.
- Publish, rollback and versions APIs.
- XML-curl serves only Published XML.
- Normal saves cannot inject `published_*` fields.
- Tenant scope is captured as `published_tenant`.
- Flow context must match the Tenant default context.
- Call-setup cache with whole-document Redis entries, after-commit invalidation
  and last-known-good fallback.
- Best-effort `reloadxml` after publish and rollback.

### Tenant layer

- `FS Tenant` and `FS Tenant Member`.
- Tenant selector and Tenants panel.
- Tenant fields on Flows, extensions, gateways, queues and DIDs.
- One SIP domain and one default context per Tenant.
- Tenant-level outbound caller ID and music-on-hold overrides.
- Tenant-qualified document names for extensions, queues, gateways and Flows;
  natural keys are unique within a Tenant instead of globally.
- Directory resolution by domain; dialplan resolution by context.
- Context wins when domain and context disagree.
- Unknown labels fall back to the configured default Tenant.
- Membership roles:
  - `Admin` — configuration, publish and rollback
  - `Supervisor` — configuration read and live operations
  - `Agent` — own extension
- Projected `FS Switch Admin`, `FS Switch Supervisor` and `FS Switch Agent`
  roles with row-level isolation.
- System Manager override.
- Default Tenant cannot be disabled or deleted.
- DID inventory: number, Tenant, enabled flag, optional assigned Flow and
  description.
- Global `callcenter.conf` contains every enabled Tenant, with
  context-qualified queue and agent names.

### Live workspace

- ESL listener publishes call, agent and registration events.
- Console subscribes through Socket.IO and keeps polling only as a disconnected
  fallback.
- Live channels, registrations and agents.
- Hangup, transfer, answer, hold, agent status and reload actions.
- Live actions are checked against the Tenant.
- Realtime events go only to the owning Tenant’s Admins/Supervisors and System
  Managers.

### Endpoint seed

- `get_softphone_config` returns only the caller’s own credentials.
- **My extension** page shows extension, Tenant, context, SIP domain, agent
  status, WebRTC URL and the SIP password behind a reveal button.

### UI and security

- Left system tree, tabbed workspace and Vue Flow canvas.
- Role-aware navigation and read-only states.
- Shared-secret XML-curl endpoint.
- SIP and ESL passwords remain password fields.
- Published XML is server-managed and read-only in the console.
- Frappe-style neutral theme across the shell, tables, forms and dialogs.
- Deep interaction QA passed for the semantic canvas, property drawer, route
  simulator, publish/rollback, version history, diff drawer and raw editor.
- Responsive 375/768 drawer layouts, keyboard focus return, named icon actions
  and axe critical/serious checks are clean for the tested pages.

## Partial

### Contact centre

Have:

- Queues, agents, tiers, strategies, max wait, music on hold.
- Backup queues.
- Live agent status changes.
- Self-service Available / On Break / Logged Out status from **My extension**.
- Supervisor wallboard with queue depth, wait, answer/abandon counters, agent
  availability and active call paths.

Missing:

- Hold-time history and per-agent daily metrics.
- Push updates for queue metrics; the wallboard refreshes every 10 seconds.
- Supervisor listen / whisper / barge.
- Call-path highlighting on the flow canvas.
- Queue events beyond agent status changes.

### Carrier layer

Have:

- Basic `FS Gateway` CRUD.
- Proxy, registration, credentials, caller ID and codec string.

Missing:

- Carrier templates and SIP profiles.
- ACL management and TLS workflow.
- Codec profile UI.
- Failover ranking.
- LCR engine, rate decks, CSV import, effective dates and currency/precision.
- Quality or time-of-day carrier preferences.
- Carrier route tester.

### Logic layer

Have:

- IVR menu, time condition, ring group, queue, voicemail, transfer,
  conference, park, set, sleep, record and hangup.
- Branching, validation, simulator, publish and rollback.

Missing:

- Holiday calendar node.
- General collect-digits node with min/max digits and terminators; `menu`
  currently collects a single digit.
- Webhook node.
- AI-agent node.
- Reusable flow blocks or subflows.
- Call screening.
- DID starting nodes in the canvas.
- Media manager, upload, transcoding and prompt versioning.
- TTS and ASR adapters.
- Recording retention, consent and PII policy.
- Live conference allocator with mute/kick.

### Tenant layer

Have:

- Tenant model, domains, contexts, membership roles, isolation and selector.
- DID inventory.
- Global callcenter document.
- Per-Tenant uniqueness for extension numbers, queue names, gateway names and
  Flow titles, backed by a name migration.

Missing:

- Broader tenant-scoped settings such as recording policy and voicemail
  defaults.
- Tenant quotas and limits.
- Tenant-level audit and reporting.
- Tenant provisioning workflow.

### Live workspace

Have:

- Event-driven live grids.
- Socket.IO push with polling fallback.
- Basic supervisor actions.
- Supervisor wallboard with queue depth, configured wait, answer/abandon
  counters, available/busy agents and active call paths.
- Queue depth from active callcenter channels and wallboard summary in the live
  snapshot.

Missing:

- Supervisor listen / whisper / barge.
- Longest-wait and hold-time collection for callers when FreeSWITCH does not
  expose queue join variables on the channel snapshot.
- Presence and screen pop.
- Live conference controls.

### Endpoint layer

Have:

- `get_softphone_config`.
- My extension credentials page.

Missing:

- Embedded WebRTC softphone widget.
- JsSIP or SIP.js integration.
- WSS, STUN and TURN configuration.
- Presence and screen pop.
- In-console call controls.
- Credential rotation.
- Device/profile management.
- Optional Helpdesk integration.

## Not started

- LCR, rate decks and carrier templates.
- SIP profiles, ACLs and TLS workflow.
- Supervisor listen/whisper/barge.
- Embedded softphone.
- Call logs / CDR.
- Recording storage and retention.
- Voicemail mailbox UI and voicemail-to-email.
- Holiday calendar.
- Webhook and AI nodes.
- Media manager, TTS and ASR.
- Tenant quotas and deeper tenant settings.

## Live acceptance result

A local Docker acceptance run on 2026-10-23 passed:

- `bench migrate` and creation of `FS Tenant`, `FS Tenant Member` and `FS DID`.
- Creation of `FS Switch Admin`, `FS Switch Supervisor` and `FS Switch Agent`.
- Membership projection and row-level isolation across two Tenants.
- Admin, Supervisor and Agent role matrix; Agent own-extension access.
- DID normalization and Tenant/Flow assignment.
- Publish and Published status for two Flows.
- Directory, dialplan and callcenter handler separation by Tenant.
- HTTP XML-curl cold and warm cache, wrong secret returns 403.
- Global `callcenter.conf` containing the acceptance queue and agent.
- Socket.IO handshake, session-cookie authentication and realtime delivery.
- A loopback call event delivered end-to-end from ESL listener to Socket.IO.
- ESL live data and agent status changes.
- Realtime recipient separation by Tenant.
- Authenticated `/fs-switch` HTML and built `app.js` served with HTTP 200.
- Login from `/login` lands on `/fs-switch`; the site home page and FS Switch
  roles point at the console.
- Browser QA: Admin Overview, Tenant switch, DIDs, Tenants panel, Dialplans
  list, and Live Agents.
- Browser QA: Agent-only navigation, My extension, password reveal and
  self-service status change.
- Browser QA: Supervisor-only navigation, live Agent status change and
  Tenant-scoped lists.
- Tenant-qualified migration for extensions, queues, gateways and Flow titles;
  duplicate natural keys are rejected inside one Tenant and allowed across
  Tenants.
- Directory and `callcenter.conf` still use natural extension and queue names
  after the document-name migration.
- Wallboard shows queue depth, configured wait, answer/abandon counters,
  available/busy agents and active call paths from the live snapshot.

Observed limitation:

- With MariaDB stopped, the HTTP XML-curl request returned 500 before the
  handler ran because Frappe’s request middleware needs MariaDB. The handler
  cache and secret hash work only inside an executing request; they are not a
  full database-outage workaround.

Still pending:

- A real FreeSWITCH call lab: menu, timeout, loop, queue transfer and variable
  persistence.
- A real multi-Tenant queue call and SIP/queue event fan-out.
- Live Tenant isolation with real SIP channels and agents.

### Deep interaction QA result

QA on 2026-10-23 found and fixed: simulator results being cleared by the
validation watcher, version drawers overflowing at 375px, focus not returning
after drawer close, unnamed icon/tree/drawer controls and low-contrast text. The
semantic canvas, property drawer, simulator, publish/rollback, version history,
diff drawer and raw editor now pass. Axe reports no critical or serious
violations on the tested list/editor/drawer states; empty table headers remain
a minor warning.

## Recommended next order

1. **Close residual live verification** - browser QA, a real FreeSWITCH call
   lab and real ESL event fan-out. The checklist is in
   [`ACCEPTANCE.md`](ACCEPTANCE.md).
2. **Finish the Tenant layer** - broader Tenant settings, quotas and
   provisioning.
3. **Supervisor depth** - listen/whisper/barge, richer hold-time history and
   agent self-service controls on top of the wallboard.
4. **Embedded WebRTC softphone** - JsSIP/SIP.js, WSS, STUN/TURN, presence,
   screen pop and call controls.
5. **Media and logic depth** — media manager, holiday calendar, collect digits,
   webhook, TTS/ASR and AI nodes.
6. **Carrier layer** — templates, SIP profiles, ACLs, failover, then LCR and
   rate decks.
7. **Call records** — CDR, recordings, voicemail mailboxes and retention.

The original thesis’s cornerstone — semantic graph, compiler, validation and
safe publishing — is complete. The remaining product gap is concentrated in
carrier routing, supervisor depth, media and the embedded endpoint.
