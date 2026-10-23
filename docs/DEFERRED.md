# Deferred work

Items intentionally outside the current slice. Keep this list short; move an
item into a plan when it becomes the next slice.

## Blocked on a live bench

- Run `bench --site ... migrate` and smoke-test the default Tenant, Tenant role
  patch, membership role sync, permission hooks and tenant-scoped counts.
- Replay a captured XML-curl POST with the cache cold, warm and MariaDB down,
  including a domain-only directory request and a context-only dialplan request.
- Verify Socket.IO authentication, namespace `/<site>`, CORS, session cookies
  and the public socket URL/port in a browser.
- Lab-test generated semantic XML in FreeSWITCH: menu, timeout, loop, queue
  transfer and variable persistence across transfers.
- Visually QA the semantic canvas, editor and list diff drawers,
  publish/rollback, versions drawer, route simulator, Tenant selector, Tenants
  panel, role-aware navigation, live events and reload warnings.
- Verify live Tenant isolation: a Supervisor in one Tenant must not see or act
  on another Tenant's channels, agents or registrations.

## Next slices

- Agent self-service page for the caller's own extension and softphone
  credentials.
- Call logs, voicemail and missed-call records.
- Embedded softphone, presence and screen pop.
- Carrier templates, failover and LCR/rate decks.
- Media library, TTS/ASR and AI-agent nodes.
- Per-Tenant uniqueness for extension numbers, queue names, gateway names and
  Flow titles.
- Import/export of dialplan graphs.

## Known limitations

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
