# Deferred work

Items intentionally outside the current slice. Keep this list short; move an
item into a plan when it becomes the next slice.

## Still needs live or lab verification

The local Docker acceptance run passed migration, role projection, tenant row
isolation, DID creation, publishing, XML-curl cold/warm requests, Socket.IO
authentication and delivery, ESL live data and agent status changes. Remaining:

Real WebRTC registration, timeout routing, menu digit, loop, queue transfer,
variable persistence, multi-Tenant queue calls and supervisor monitor actions
passed. Remaining:

- Real registration event fan-out with multiple Tenants.
- Simultaneous multi-Tenant calls with Socket.IO recipient isolation.
- Verify a Supervisor in one Tenant cannot act on another Tenant's live
  channels or agents; API live-data isolation passed with an Acceptance B
  queue call.

## Next slices

- Call logs, voicemail and missed-call records.
- Embedded softphone, presence and screen pop.
- Carrier templates, failover and LCR/rate decks.
- Media library, TTS/ASR and AI-agent nodes.
- Broader Tenant settings for recording policy, voicemail defaults and quotas.
- Import/export of dialplan graphs.

## Known limitations

- A full MariaDB outage fails at Frappe’s HTTP middleware before the XML-curl
  handler runs. The handler cache and secret hash only protect compiler or
  lookup failures inside an executing request.
- The route simulator does not evaluate native FreeSWITCH time fields (`wday`,
  `hour`, `minute-of-day`); use `${strftime(...)}` or a `set` variable.
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
