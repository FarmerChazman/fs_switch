# Deferred work

Items intentionally outside the current slice. Keep this list short; move an
item into a plan when it becomes the next slice.

## Blocked on a live bench

- Run `bench --site ... migrate` and smoke-test the default Tenant patch,
  tenant-scoped counts, publish, rollback, versions, diff and the route
  simulator.
- Replay a captured XML-curl POST with the cache cold, warm and MariaDB down.
- Lab-test generated semantic XML in FreeSWITCH: menu, timeout, loop, queue
  transfer and variable persistence across transfers.
- Visually QA the semantic canvas, editor and list diff drawers,
  publish/rollback, versions drawer, route simulator, tenant fields and reload
  warnings.

## Next slices

- Tenant UI, domain/context mapping and tenant-scoped role access.
- ESL realtime fan-out to replace polling as the primary live-state path.
- Call logs, voicemail and missed-call records.
- Embedded softphone, presence and screen pop.
- Carrier templates, failover and LCR/rate decks.
- Media library, TTS/ASR and AI-agent nodes.
- Role-based console access for agent, supervisor and administrator.

## Known limitations

- The route simulator does not evaluate native FreeSWITCH time fields (`wday`,
  `hour`, `minute-of-day`); use `${strftime(...)}` or a `set` variable.
- Single-tenant alpha: tenant fields exist and call-setup documents are filtered
  by tenant, but every domain and context resolves to tenant `default`.
- Tenant fields are fixed after creation, but tenant-scoped create permissions
  are not enforced yet. A user who can create a document can choose another
  Tenant until tenant-scoped roles land.
- Extension numbers, queue names, gateway names and Flow titles are globally
  unique; per-tenant uniqueness is deferred until the tenant UI.
- Semantic flow catch-all protection is not validated yet.
- Extension name and destination pattern are not stored in the published
  snapshot; the diff shows them through the XML diff.
- The console polls live state every five seconds. The ESL listener publishes
  realtime events, but the console does not subscribe to them yet.
