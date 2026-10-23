# ADR 0001: Frappe is the control plane; FreeSWITCH is the data plane

**Status:** accepted
**Date:** 2026-10-23

## Context

FS Switch needs a browser console, a configuration store, authentication,
permissions, audit trails, realtime events and a low-level interface to
FreeSWITCH. The source notes considered Frappe, Laravel, Go and a separate Node
backend.

FreeSWITCH must remain the SIP/RTP/media engine. Putting Frappe in the media
path would add latency and failure modes to every call. A second general-purpose
backend would duplicate identity, permissions, storage and deployment.

## Decision

1. **Frappe v16 is the control plane.** The `fs_switch` app owns DocTypes,
   validation, permissions, audit, the XML-curl endpoints and realtime
   publishing.
2. **FreeSWITCH is the data plane.** `mod_sofia`, `mod_callcenter`, media
   applications and the ESL event stream stay in FreeSWITCH. Voice media does
   not traverse Frappe.
3. **The console is Vue 3 + PrimeVue + Vue Flow.** It is served as a Frappe app
   page at `/fs-switch`; it uses Frappe REST, whitelisted methods and the
   existing Socket.IO/Redis realtime layer.
4. **Configuration is served through `mod_xml_curl`.** Frappe answers the
   directory, dialplan and `callcenter.conf` bindings. The endpoint is
   guest-accessible with a constant-time shared-secret check because
   FreeSWITCH cannot log in to Frappe.
5. **Live state and actions go through ESL.** Commands use short-lived
   connections and a whitelist. A long-running listener subscribes to channel
   and call-center events and publishes them on Frappe realtime channels.
6. **There is no second backend.** A small Python module inside the Frappe app
   is preferred over a new service. Long-running work is queued or handled by
   the listener, not by a web request.
7. **The browser never talks to ESL directly.** All actions are authenticated by
   Frappe, checked against roles, and executed server-side.

## Consequences

### Positive

- One identity, one permission model and one audit trail.
- The console can use Frappe's existing session, CSRF and realtime plumbing.
- The deployment stays small: Frappe, MariaDB, Redis and FreeSWITCH.
- The same data model can later serve Desk, Helpdesk and external API clients.

### Negative / risks

- Frappe becomes a high-value target. It must enforce tenant isolation and
  command permissions carefully.
- The XML-curl endpoint is on the call-setup path and must be fast and
  fail-safe. A Frappe outage must not take down all call routing; a cached
  last-known-good XML response is required before production.
- ESL sockets are stateful. The listener must be supervised, reconnect
  automatically and never block a web worker.
- Frappe's realtime layer is not a queue. High-volume call events need
  throttling and aggregation before they reach the browser.

## Implementation notes

- `apps/fs_switch/fs_switch/api.py` exposes XML-curl, console methods and the
  softphone configuration.
- `apps/fs_switch/fs_switch/esl.py` contains the dependency-free ESL client and
  command whitelist.
- `apps/fs_switch/fs_switch/esl_listener.py` publishes normalized call and agent
  events.
- `apps/fs_switch/frontend/` is the Vue console.
- Production should use HTTPS/WSS and keep ESL off the public network.

## Rejected alternatives

- **Separate Node/Go control API:** duplicates identity, permissions, audit and
  deployment; adds a service to operate.
- **Direct browser-to-ESL:** exposes a privileged control socket and bypasses
  Frappe permissions.
- **Frappe in the media path:** adds latency and a new failure domain to every
  call.
- **Hand-edited XML as the primary interface:** no validation, no safe publish,
  no tenant isolation and no usable audit trail.
