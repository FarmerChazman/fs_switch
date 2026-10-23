# Changelog

## 0.1.0 — unreleased

- Initial standalone FS Switch app.
- Frappe DocTypes for settings, extensions, gateways, queues and dialplans.
- `mod_xml_curl` directory, dialplan and `callcenter.conf` endpoints.
- ESL command client and realtime event listener.
- Vue 3 + PrimeVue console with tree navigation, tabbed forms, live grids and a
  Vue Flow dialplan editor.
- Semantic flow schema v1, node registry, strict validation and a branching
  compiler alongside the original raw-application graph format.
- Semantic flow canvas with an intent-level palette, typed digit/timeout and
  match/no-match output ports, property drawer, live validation and unsaved XML
  preview. Semantic flows are the default creation path; raw application chains
  remain available as an advanced editor.
- Draft/published Flow lifecycle with immutable published versions, publish and
  rollback APIs, a versions drawer, and xml-curl serving only Published XML.
  Existing valid Flows are published by a one-time upgrade patch.
- Call-setup path cache for directory, dialplan and `callcenter.conf` with
  tenant/context keys, after-commit invalidation, a last-known-good fallback and
  FreeSWITCH's not-found document when no good XML exists. Publish and rollback
  reload FreeSWITCH best-effort.
- Route simulator for semantic Flows: destination, simulated time and caller
  digits in; node path, chosen ports, terminal step and warnings out. The
  simulator walks the Draft graph, never the XML, and is available in the
  semantic editor's Simulate tab.
- Draft-versus-Published diff for every Flow: settings, entry step, added,
  removed and changed steps and connections, plus a unified XML diff. Canvas
  positions and edge ids are ignored. The diff is read-only and available from
  the Dialplans list and the semantic editor toolbar.
- Tenant model and UI: a default Tenant, tenant fields on Flows, extensions,
  queues and gateways, a top-bar Tenant selector, a Tenants panel, and
  tenant-filtered directory, dialplan and callcenter documents.
- Domain/context mapping: each Tenant owns one SIP domain and one default
  context. Directory requests resolve by domain; dialplan and callcenter requests
  resolve by context. Unknown labels fall back to the configured default Tenant.
- Tenant-scoped roles: `Admin`, `Supervisor` and `Agent` memberships project onto
  `FS Switch Admin`, `FS Switch Supervisor` and `FS Switch Agent`; row-level
  permission hooks restrict each role to its Tenants. System Manager is the
  global override. A migration creates the roles and reconciles memberships; the
  default Tenant cannot be disabled or deleted.
- Socket.IO live updates: the ESL listener publishes call, agent and
  registration events with Tenant metadata to the owning Tenant's Admins and
  Supervisors plus System Managers; the console applies them directly and keeps
  a 30-second snapshot poll only while disconnected.
- Published XML, version history and tenant scope are server-managed. A normal
  save cannot inject `published_*` fields or move a document to another Tenant;
  the served dialplan is filtered by `published_tenant`. A Flow context must
  match its Tenant's default context.
- Product brief and architecture decision records for the control-plane,
  semantic-flow and multi-tenant direction.
- Public documentation set: install and feature README, docs index, operations
  guide, development guide, security policy and deferred-work list.
- Docker Desktop development stack with Frappe and FreeSWITCH.
