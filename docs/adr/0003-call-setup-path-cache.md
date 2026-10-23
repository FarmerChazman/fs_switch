# ADR 0003: Cache whole documents on the call-setup path

**Status:** accepted
**Date:** 2026-10-23

## Context

FreeSWITCH blocks while it asks `mod_xml_curl` for the directory, dialplan and
`callcenter.conf`. A handler that queries several DocTypes or compiles a Flow
inside the request adds latency to every call setup, and a handler that raises
drops the call.

The published dialplan is already compiled and stored in `FS Dialplan
.published_xml`. The remaining cost is assembling the document and reading it
from MariaDB. Directory and `callcenter.conf` are rendered from a handful of
documents and change less often than calls arrive.

Frappe already runs Redis for cache and realtime. A second cache service would
violate the no-second-backend invariant.

## Decision

1. **Cache the whole document, not fragments.** Each handler stores the exact
   XML body it will return under
   `fs_switch:xml:current:<kind>:<tenant>:<name>`. A hit performs no database
   query and no compilation.
2. **The key carries tenant and routing label.** `<kind>` is `dialplan`,
   `directory` or `callcenter`; `<name>` is the context or domain. A cached
   routing map of enabled Tenants resolves a SIP domain or context to its
   Tenant. If both labels are supplied and disagree, context wins; unknown
   labels fall back to the configured default Tenant. The map is cached in
   Redis and invalidated after commit. The global `callcenter.conf` document
   uses the fixed key `all/all`.
3. **Last-known-good is a separate key with no expiry.**
   `fs_switch:xml:last-known-good:<kind>:<tenant>:<name>` is written after every
   build that produced a document. A build that yields no document (for example
   every Flow is disabled) is cached as not-found for the current key but does
   not erase the last-known-good document. Invalidation deletes only the current
   key, so a database or compiler failure serves the last document that built
   successfully.
4. **No last-known-good means not-found.** The handler returns
   `<document type="freeswitch/xml"><section name="result"><result status="not
   found"/></section></document>` rather than an empty document.
5. **Handlers never invalidate.** They may read the cache, fill the current and
   last-known-good entries on a miss, read documents, and return XML. A cache
   read or write failure is logged and ignored; the handler still builds and
   returns a document.
6. **The shared secret hash is cached in Redis.** An executing handler can
   authenticate FreeSWITCH while MariaDB is unavailable, then serve
   last-known-good XML. Frappe’s request middleware still needs MariaDB, so a
   full outage can fail before the handler runs. If neither Redis nor MariaDB
   can provide the hash, the handler fails closed with `Forbidden`.
7. **The control plane invalidates after commit.** Publish, rollback,
   enable/disable, settings changes, Tenant changes and extension/queue changes
   register an after-commit invalidation. Invalidating before commit would let a
   concurrent request rebuild the cache from the old row and leave it stale.
8. **Publish reloads FreeSWITCH best-effort.** After the commit and cache
   invalidation, `publish_dialplan` and `rollback_dialplan` call `reloadxml`. A
   failed reload is reported in the response and does not roll back the publish.
9. **The current key expires after 24 hours.** This bounds staleness if an
   invalidation is lost. Last-known-good does not expire.

## Consequences

### Positive

- A warm call setup performs a cached tenant lookup, one document cache read and
  the shared-secret check; no MariaDB query and no compilation.
- A compiler or lookup failure inside an executing request degrades to the last
  good XML, not to an empty dialplan. A full MariaDB outage is still a Frappe
  availability failure at the HTTP layer.
- Publish, rollback and enable/disable are the only operations that change what
  is served, and they are explicit.
- Tenant scoping is in place on documents and cache keys; domain/context mapping
  changes only the resolver, not the handler or key shape.

### Negative / risks

- The whole document is rebuilt when any input changes. That is acceptable at
  current document counts; per-context invalidation is a later optimization.
- Redis becomes part of the serving path. A Redis outage falls back to building
  from MariaDB, which is slower but still correct.
- Last-known-good can serve a flow that was later disabled if the rebuild fails.
  This is the intended fail-safe: a known-good dialplan is safer than no routing.
- Directory changes made directly in the database bypass controller events and
  stay cached until the 24-hour expiry or the next invalidation.

## Test strategy

- Unit-test cache hit, miss, invalidation, build failure with and without
  last-known-good, and cache-store failure with an in-memory store.
- Test the handler with a fake Frappe module: published XML is served from cache,
  a database failure serves last-known-good, and no published flows return
  not-found.
- Replay a captured XML-curl POST against a real site with the cache cold, warm
  and MariaDB unavailable before production.

## References

- [Architecture](../architecture.md)
- [Flow model](../flow-model.md)
- [ADR 0001: Frappe control plane](0001-frappe-control-plane.md)
- `apps/fs_switch/fs_switch/call_setup.py`
- `tests/test_call_setup.py`
