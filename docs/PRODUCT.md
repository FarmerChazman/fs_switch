# FS Switch product brief

**Status:** accepted direction, v0.1
**Last updated:** 2026-10-23
**Source notes:** [`FreeSWITCH UI.txt`](FreeSWITCH%20UI.txt), [`world-class FreeSWITCH UI layout idea.txt`](world-class%20FreeSWITCH%20UI%20layout%20idea.txt)

## 1. Product statement

FS Switch is the Frappe-native control plane that makes FreeSWITCH usable by
telecom administrators, supervisors and agents without hiding FreeSWITCH from
the engineers who operate it.

It is a visual, real-time, tenant-scoped call-control product:

- configuration lives in Frappe, not in hand-edited XML;
- call flows are designed as intent-level graphs;
- FreeSWITCH remains the media and routing engine;
- XML is a compiled artifact, not the editing surface;
- every change is validated, auditable and reversible;
- live calls and agents are visible and controllable in the same console.

The product promise is:

> **FreeSWITCH power. SaaS ease. Frappe as the single source of truth.**

## 2. The problem

FreeSWITCH is an enterprise software-defined telecom engine. It handles SIP,
RTP, media, call-center queues, conferencing, IVRs and high-volume event
streams. Its power is exposed through XML, CLI commands and ESL events.

That creates three problems:

1. **The configuration is expert-only.** A simple after-hours route can require
   nested XML conditions, channel variables, priorities and transfer semantics.
2. **The tools are fragmented.** Configuration, live monitoring, supervision
   and softphone controls usually live in different products with different
   identities and permissions.
3. **Changes are risky.** Editing live XML has no validation, no diff, no
   rollback and no tenant-scoped audit trail.

FS Switch solves those problems by putting a semantic control plane in front of
FreeSWITCH and keeping the engine intact.

## 3. Who it is for

| Persona | What they need |
|---|---|
| **Platform administrator** | Install, connect Frappe to FreeSWITCH, manage trunks, security and upgrades. |
| **Telecom administrator** | Create numbers, extensions, queues, IVRs and routing without writing XML. |
| **Contact-center supervisor** | See queue state, agent state and active calls; listen, whisper, barge or reassign. |
| **Agent** | Use a browser softphone, see presence, receive screen pops and control calls. |
| **Senior engineer** | Inspect the generated XML, raw application nodes, logs and events when debugging. |

The first release should make the telecom administrator productive. The
supervisor and agent experiences are the next expansion, not an afterthought.

## 4. Product principles

1. **Intent over XML.** The default editor exposes call-flow concepts, not
   FreeSWITCH application names. Raw applications and XML remain available in an
   advanced view.
2. **One graph, three projections.** The same canonical flow is shown as a
   canvas, a table and compiled XML. The projections must not drift.
3. **Safe by default.** A flow is validated before it is saved or published.
   Invalid flows never reach FreeSWITCH.
4. **Frappe is the control plane.** Identity, permissions, audit, versioning,
   realtime events and storage stay in Frappe. No second backend.
5. **FreeSWITCH is the data plane.** Voice media does not traverse Frappe.
6. **Tenant-ready from the start.** The first UI may expose one organisation, but
   the data model must be able to scope numbers, trunks, flows, queues and roles
   by tenant without a migration.
7. **Progressive disclosure.** A junior administrator sees simple forms; a
   senior engineer can open the table, the raw-app graph and the XML.
8. **Real-time by default.** Socket.IO events drive live state; polling is a
   fallback, not the primary contract.
9. **Carrier-grade means observable.** Every publish, reload, call action and
   permission decision is auditable.

## 5. The five pillars

### 5.1 Carrier layer

Trunks and gateways, SIP profiles, codecs, caller ID, failover, ACLs and
least-cost routing.

The first release needs reliable gateway CRUD and generated XML. LCR, rate
decks and carrier quality ranking are a later subsystem.

### 5.2 Tenant layer

Organisations, domains, contexts, DIDs, extensions, ring groups and voicemail.

The console now has a Tenant selector and a Tenants panel. Each Tenant owns one
SIP domain and one default context; directory requests resolve by domain and
dialplan/callcenter requests resolve by context. Tenant membership projects onto
Admin, Supervisor and Agent roles, and row-level hooks restrict configuration
and live operations to the right Tenants. A user may belong to more than one
Tenant; the active Tenant is a UI choice, not a permission bypass.

### 5.3 Logic layer

Visual IVRs, time and holiday routing, digit menus, ring groups, queues,
voicemail, transfers, media prompts and later TTS/ASR/AI agents.

This is the product's core. A visual editor without a correct compiler is only a
drawing tool.

### 5.4 Live workspace

Channels, registrations, queues, agents, call-path highlighting, wallboards and
supervisor actions.

The ESL listener publishes call, agent and registration events with Tenant
metadata. The console consumes them over Socket.IO and keeps a 30-second
snapshot poll as a disconnected fallback.

### 5.5 Endpoint layer

Embedded WebRTC softphone, presence, screen pop, call controls and credential
lifecycle.

The current `get_softphone_config` endpoint is the seed. The reusable softphone
component belongs to FS Switch; Helpdesk integration is optional.

## 6. The first release: semantic core

The first product milestone is not a prettier console. It is the foundation
that makes every later screen trustworthy.

**Goal:** a telecom administrator can create a branching inbound flow, see the
compiled XML, and know that invalid routes are rejected before FreeSWITCH sees
them.

In scope:

- canonical semantic flow schema v1;
- node registry for answer, play, menu, time, ring group, queue, voicemail,
  transfer, hangup, conference, park, set, sleep and record;
- edge ports and branch handles;
- strict validation for missing routes, unknown handles, unreachable nodes and
  invalid terminal edges;
- deterministic XML compilation;
- semantic canvas with typed output ports and property drawers;
- route simulator that walks the Draft graph with destination, time and digits;
- draft/publish/rollback with immutable published versions;
- raw-graph compatibility for existing dialplans;
- unit tests and golden XML checks.

Out of scope for this milestone:

- LCR;
- media transcoding, TTS and ASR;
- supervisor listen/whisper/barge;
- embedded softphone;
- call logs and CDR reporting.

## 7. Success measures

For the semantic core:

- a valid flow compiles to deterministic XML;
- an invalid flow returns actionable errors, not a FreeSWITCH failure;
- existing raw dialplans continue to compile unchanged;
- every semantic node has a unit test for its generated action or branch;
- branching flows compile without duplicating the whole downstream graph.

For the product:

- a new administrator can create a number, a menu, a queue and an after-hours
  route without editing XML;
- a supervisor can see a live queue and intervene without leaving the console;
- a senior engineer can inspect the generated XML and explain any route;
- every published change has an author, a timestamp, a diff and a rollback path.

## 8. Roadmap

| Phase | Theme | Outcome |
|---|---|---|
| **0** | Foundation | Product brief, ADRs, semantic schema v1, compiler and tests. |
| **1** | Semantic editor | Node palette, property drawer, ports, validation panel, XML preview. |
| **2** | Safe publishing | Draft/published versions, rollback, call-setup cache, last-known-good, reload, route simulator and Draft-versus-Published diff are in place. |
| **3** | Tenant layer | Tenant UI, domain/context mapping, membership roles, DID inventory and row-level Tenant isolation are in place. |
| **4** | Carrier layer | Gateway templates, failover and LCR/rate decks. |
| **5** | Live workspace | Socket.IO call, agent and registration events, Tenant-filtered live state and supervisor actions. |
| **6** | Endpoint layer | Embedded softphone, presence, screen pop and call controls. |
| **7** | Media and AI | Prompt library, transcoding, TTS, ASR and AI-agent nodes. |

## 9. Decisions and assumptions

- **Tenant-scoped by default.** Every configuration document and live row
  resolves to a Tenant. The console selects one active Tenant at a time; System
  Manager can switch across all of them.
- **Semantic graph is canonical.** Raw FreeSWITCH application graphs remain an
  advanced/import format, not the primary product model.
- **State-machine compilation.** Each semantic node compiles to a named
  FreeSWITCH extension; edges compile to transfers. This supports branches,
  joins and loops without path explosion.
- **XML-curl must fail safely.** It is on the call-setup path and serves whole
  documents from cache, with a last-known-good fallback and a cached secret hash
  for handler-level failures. Frappe’s HTTP middleware still needs MariaDB, so a
  full database outage is not transparently survived.
- **No second backend.** Do not introduce Laravel, Go or a separate Node service
  for FreeSWITCH control.

## 10. References

- [Architecture](architecture.md)
- [Semantic flow model](flow-model.md)
- [ADR 0001: Frappe control plane](adr/0001-frappe-control-plane.md)
- [ADR 0002: Semantic flow graph](adr/0002-semantic-flow-graph.md)
- [ADR 0003: Call-setup path cache](adr/0003-call-setup-path-cache.md)
- [Console UI notes](ui.md)
