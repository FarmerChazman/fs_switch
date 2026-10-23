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
- Tenant-ready data model: a default Tenant, tenant fields on Flows, extensions,
  queues and gateways, and tenant-filtered directory, dialplan and callcenter
  documents. The alpha resolves every domain and context to `default`.
- Published XML, version history and tenant scope are server-managed. A normal
  save cannot inject `published_*` fields or move a document to another Tenant;
  the served dialplan is filtered by `published_tenant`.
- Product brief and architecture decision records for the control-plane,
  semantic-flow and multi-tenant direction.
- Public documentation set: install and feature README, docs index, operations
  guide, development guide, security policy and deferred-work list.
- Docker Desktop development stack with Frappe and FreeSWITCH.
