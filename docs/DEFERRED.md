# Deferred work

Items intentionally outside the current slice. Keep this list short; move an
item into a plan when it becomes the next slice.

## Still needs live or lab verification

The local Docker acceptance run passed migration, role projection, tenant row
isolation, DID creation, publishing, XML-curl cold/warm requests, Socket.IO
authentication and delivery, ESL live data and agent status changes. Remaining:

- Deep interaction QA of the semantic canvas, property drawer, route simulator,
  publish/rollback drawer and diff drawer. Admin, Supervisor and Agent pages,
  Tenant switching, DIDs, Tenants, Live Agents and My extension were visually
  checked in a browser.
- Lab-test generated semantic XML in FreeSWITCH: menu, timeout, loop, queue
  transfer and variable persistence across transfers.
- Lab-test multi-Tenant `callcenter.conf` queues and agents with a real call.
- Loopback `CHANNEL_STATE` fan-out through ESL listener and Socket.IO passed;
  still verify event delivery for real SIP calls, queue calls and registrations.
- Verify a Supervisor in one Tenant cannot see or act on another Tenant's live
  channels or agents with real calls.

## Next slices

- Call logs, voicemail and missed-call records.
- Embedded softphone, presence and screen pop.
- Carrier templates, failover and LCR/rate decks.
- Media library, TTS/ASR and AI-agent nodes.
- Per-Tenant uniqueness for extension numbers, queue names, gateway names and
  Flow titles.
- Broader Tenant settings for recording policy, voicemail defaults and quotas.
- Import/export of dialplan graphs.

## Known limitations

- A full MariaDB outage fails at Frappe’s HTTP middleware before the XML-curl
  handler runs. The handler cache and secret hash only protect compiler or
  lookup failures inside an executing request.
- The route simulator does not evaluate native FreeSWITCH time fields (`wday`,
  `hour`, `minute-of-day`); use `${strftime(...)}` or a `set` variable.
- Extension numbers, queue names, gateway names and Flow titles are globally
  unique. A multi-Tenant deployment cannot reuse `1001` or `sales` across
  Tenants yet.
- Tenant roles are projected after commit. A user may need to reload the console
  after a membership change before the new role is visible.
- Role projection is additive at the Frappe role level; row-level hooks are what
  separate Tenants. A user who is an Admin in one Tenant and an Agent in another
  keeps `FS Switch Admin`, but only sees Admin rows in the first Tenant.
- Semantic flow catch-all protection is not validated yet.
- Extension name and destination pattern are not stored in the published
  snapshot; the diff shows them through the XML diff.
- The socket path is verified in code and by the frontend build, but not yet
  against a live Frappe Socket.IO server.
- Live fan-out resolves the Tenant's recipient users per event. Cache the
  recipient list if FreeSWITCH event volume becomes high.
