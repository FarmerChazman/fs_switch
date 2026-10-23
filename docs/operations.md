# Operating FS Switch

This guide is for the person running FS Switch after installation. It assumes
the console and XML-curl endpoint are already reachable from FreeSWITCH.

## Login and landing page

The app sets the site **Website Settings > home_page** to `fs-switch` when it is
blank, and gives `FS Switch Admin`, `FS Switch Supervisor` and `FS Switch Agent`
a role home page of `/fs-switch`. A normal login therefore lands in the console,
not the blank Desk Framework page. System Managers can still open **Open Desk**
from the console; their landing page follows the site home page unless they have
an explicit role home page.

## Health checks

| Check | What to do |
|---|---|
| Frappe is up | `curl -fsS https://<site>/api/method/ping` |
| FreeSWITCH is reachable over ESL | Open the console; the top bar shows **FreeSWITCH connected**. |
| Live state is readable | `bench --site <site> execute fs_switch.api.get_live_data` as an administrator. |
| XML-curl is reachable | Request the dialplan endpoint with the shared secret; see below. |
| ESL listener is running | Check the service or `logs/esl-listener.log` in Docker. |

If host RTP ports `16384-16484/udp` are already in use, set
`FS_SWITCH_RTP_START` and `FS_SWITCH_RTP_END` to a free range before starting
the stack.

A minimal XML-curl check:

```bash
curl 'https://<site>/api/method/fs_switch.api.xml_curl?secret=<secret>&section=dialplan'
```

The response is a FreeSWITCH XML document. If no Published Flow exists and no
last-known-good cache entry exists, the result is FreeSWITCH's `not found`
document, not an empty dialplan.

## Publish workflow

1. Edit the Flow and save the Draft.
2. Let validation pass. Every non-terminal output must be connected.
3. Run **Simulate** with a destination, time and caller digits.
4. Open **Draft vs Published** and review the graph and XML diff.
5. Publish. The response includes the new version and the `reloadxml` result.
6. Verify the call path. A failed `reloadxml` does not fail the publish; run
   `reloadxml` from `fs_cli` if FreeSWITCH did not pick up the change.

XML-curl serves only the Published version. Enabling or disabling a Flow is
operational and does not require a new publish.

## Rollback

Rollback repoints the Published version to an earlier immutable version. The
Draft is preserved, so in-progress edits are not lost. If the Draft differs from
the rolled-back version, `publish_status` becomes `Draft` until it is published
again.

## Call-setup cache

The directory, dialplan and `callcenter.conf` handlers serve whole documents from
Redis:

```text
fs_switch:xml:current:<kind>:<tenant>:<name>
fs_switch:xml:last-known-good:<kind>:<tenant>:<name>
```

`callcenter.conf` uses `<tenant>=all` and `<name>=all` because it is a global
document.

- Current entries expire after 24 hours.
- Last-known-good entries have no expiry and are not overwritten by an empty
  build.
- Publish, rollback, enable/disable, settings, Tenant, extension, queue and
  gateway changes invalidate the current entry after commit.
- Handlers never invalidate. They read, fill on a miss, and return XML.
- A warm cache plus the cached secret hash keeps an executing handler alive
  during a database failure. A full MariaDB outage still fails at the Frappe
  HTTP middleware before the handler runs, so do not treat last-known-good as a
  database-outage workaround. If neither store can authenticate the request,
  the handler fails closed.

The routing map of enabled Tenants is cached in Redis at
`fs_switch:xml:tenant-map` so a warm call setup does not read MariaDB for Tenant
resolution. A Tenant change invalidates the map and the current documents after
commit.

## Tenant routing

Each enabled Tenant owns one SIP domain and one default context. Both are unique
among enabled Tenants.

- A directory request supplies a domain; the handler resolves the Tenant by
  domain.
- A dialplan request supplies a context; the handler resolves the Tenant by
  context.
- `callcenter.conf` is global, so its document includes every enabled Tenant.
- If both labels are supplied and disagree, the context wins.
- An unknown label falls back to the Tenant in **FS Switch Settings >
  default_tenant**. The default Tenant cannot be disabled or deleted. On a fresh
  install, `FS_SWITCH_DEFAULT_TENANT` names the first Tenant; on an existing
  site the slug must already exist.
- Tenant-level outbound caller ID and music-on-hold override the global
  Settings values when present.

A Flow context must match its Tenant's default context. Otherwise the compiled
Flow would be stored under a Tenant that the request cannot reach.

Assign inbound numbers in **DIDs**. The inventory is assigned to a Tenant and
optionally to the Flow expected to handle the number. The assignment is
informational; actual routing still comes from the Flow destination pattern.
Normalize numbers the way the carrier sends them: the `DID` document removes
spaces, hyphens and an optional `tel:` prefix but keeps a leading `+`.

FreeSWITCH's `callcenter.conf` configuration request is global rather than
context-scoped, so `serve_callcenter()` builds one document for every enabled
Tenant. Queue and agent names include the Tenant context, so queues from
different Tenants do not collide. Lab-test multi-Tenant queue hosting before
production use.

## ESL listener and Socket.IO

The listener subscribes to channel, call-center and registration events and
publishes them on Frappe realtime:

```text
fs_switch_call
fs_switch_agent
fs_switch_registration
```

The listener publishes each event only to the owning Tenant's Admins and
Supervisors, plus System Managers. Agents and other Tenants do not receive the
event. The console connects to the site's Socket.IO namespace (`/<site>`) and
applies events directly. It takes an initial snapshot and falls back to a
30-second snapshot poll only while the socket is disconnected.

The console derives the socket URL from the current site. If Socket.IO runs on a
separate public host or port, set it in `site_config.json`:

```json
{
  "fs_switch_socketio_url": "https://socket.example.com"
}
```

When unset, the console uses the site origin, or the site origin plus
`frappe.conf.socketio_port`. The socket port must be reachable from the browser
and must allow the site origin through CORS. Authentication uses the normal
Frappe session cookie, so serve both over HTTPS and keep them on the same site
or a trusted subdomain.

Verify the listener and socket independently:

```bash
bench --site <site> execute fs_switch.esl_listener.run
bench --site <site> execute fs_switch.api.get_live_data
```

If the socket cannot connect, the console stays on polling; live actions still
work. If events are missing but polling is current, check the listener process
and the `CUSTOM callcenter::info` subscription.

On a bench:

```bash
bench --site <site> execute fs_switch.esl_listener.run
```

Install `freeswitch/install/esl-listener.service` for a long-running service.
The Docker entrypoint starts the listener automatically. The listener reconnects
after a FreeSWITCH restart.

The Docker entrypoint sets the event-socket ACL to `lan` so the separate Frappe
container can connect over the private Docker network. The ESL port is not
published to the host. If you see `Rejected by acl "loopback.auto"`, the
FreeSWITCH event-socket ACL still excludes the Frappe container.

## Troubleshooting

| Symptom | Check |
|---|---|
| FreeSWITCH gets `not found` | Is a Flow Published and enabled? Does `published_tenant` match the resolved Tenant? Is a last-known-good entry present? |
| Calls still use old routing | Was the Flow published? Did the cache invalidate? Did `reloadxml` succeed? |
| Console says FreeSWITCH offline | ESL host, port, password and ACL; the ESL port must be reachable from Frappe, not exposed publicly. Docker uses `lan` because the default `loopback.auto` rejects the Frappe container. |
| Live state is stale | Is the ESL listener running? Is the console on **Polling fallback**? Check the Socket.IO URL, port, CORS and session cookie. |
| Publish fails | Read the validation error. The compiler rejects broken routes before version history or serving changes. |
| Publish succeeded but XML-curl is stale | Check the Redis connection, the cache key Tenant/context, and FreeSWITCH's `reloadxml`. |
| User sees an empty console | Is the user an enabled member of a Tenant? A projected `FS Switch *` role alone is not enough; the membership row is the source of truth. |
| Tenant change is rejected | SIP domains and default contexts must be unique among enabled Tenants. A Flow context must match its Tenant. |
| MariaDB outage breaks call setup | Frappe’s HTTP middleware still needs MariaDB, so a full outage can fail before the handler. Restore MariaDB; last-known-good only protects compiler or lookup failures inside an executing request. |

## Backup and recovery

- Back up MariaDB. It holds Flows, versions, extensions, queues, gateways and
  settings.
- Redis is a cache, not the source of truth. Losing it only makes the next call
  setup rebuild from MariaDB.
- Back up TLS certificates, `.env` secrets and any carrier credentials.
- Keep the AGPL source and your deployment configuration under version control.
