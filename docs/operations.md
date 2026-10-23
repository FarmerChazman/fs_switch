# Operating FS Switch

This guide is for the person running FS Switch after installation. It assumes
the console and XML-curl endpoint are already reachable from FreeSWITCH.

## Health checks

| Check | What to do |
|---|---|
| Frappe is up | `curl -fsS https://<site>/api/method/ping` |
| FreeSWITCH is reachable over ESL | Open the console; the top bar shows **FreeSWITCH connected**. |
| Live state is readable | `bench --site <site> execute fs_switch.api.get_live_data` as an administrator. |
| XML-curl is reachable | Request the dialplan endpoint with the shared secret; see below. |
| ESL listener is running | Check the service or `logs/esl-listener.log` in Docker. |

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

- Current entries expire after 24 hours.
- Last-known-good entries have no expiry and are not overwritten by an empty
  build.
- Publish, rollback, enable/disable, settings, Tenant, extension, queue and
  gateway changes invalidate the current entry after commit.
- Handlers never invalidate. They read, fill on a miss, and return XML.
- If MariaDB is down, a warm cache plus the cached secret hash can still serve
  last-known-good XML. If neither store can authenticate the request, the
  handler fails closed.

The routing map of enabled Tenants is cached in Redis at
`fs_switch:xml:tenant-map` so a warm call setup does not read MariaDB for Tenant
resolution. A Tenant change invalidates the map and the current documents after
commit.

## Tenant routing

Each enabled Tenant owns one SIP domain and one default context. Both are unique
among enabled Tenants.

- A directory request supplies a domain; the handler resolves the Tenant by
  domain.
- A dialplan or `callcenter.conf` request supplies a context; the handler
  resolves the Tenant by context.
- If both labels are supplied and disagree, the context wins.
- An unknown label falls back to the Tenant in **FS Switch Settings >
  default_tenant**. The default Tenant cannot be disabled or deleted. On a fresh
  install, `FS_SWITCH_DEFAULT_TENANT` names the first Tenant; on an existing
  site the slug must already exist.

A Flow context must match its Tenant's default context. Otherwise the compiled
Flow would be stored under a Tenant that the request cannot reach.

FreeSWITCH's `callcenter.conf` configuration request is global rather than
context-scoped. Without a context, `serve_callcenter()` uses the default Tenant.
Verify queue hosting in the lab before relying on multi-Tenant queues; see
[`DEFERRED.md`](DEFERRED.md).

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

## Troubleshooting

| Symptom | Check |
|---|---|
| FreeSWITCH gets `not found` | Is a Flow Published and enabled? Does `published_tenant` match the resolved Tenant? Is a last-known-good entry present? |
| Calls still use old routing | Was the Flow published? Did the cache invalidate? Did `reloadxml` succeed? |
| Console says FreeSWITCH offline | ESL host, port and password; the ESL port must be reachable from Frappe, not exposed publicly. |
| Live state is stale | Is the ESL listener running? Is the console on **Polling fallback**? Check the Socket.IO URL, port, CORS and session cookie. |
| Publish fails | Read the validation error. The compiler rejects broken routes before version history or serving changes. |
| Publish succeeded but XML-curl is stale | Check the Redis connection, the cache key Tenant/context, and FreeSWITCH's `reloadxml`. |
| User sees an empty console | Is the user an enabled member of a Tenant? A projected `FS Switch *` role alone is not enough; the membership row is the source of truth. |
| Tenant change is rejected | SIP domains and default contexts must be unique among enabled Tenants. A Flow context must match its Tenant. |
| MariaDB outage breaks call setup | Confirm Redis is up, the secret hash is cached and a last-known-good document exists. |

## Backup and recovery

- Back up MariaDB. It holds Flows, versions, extensions, queues, gateways and
  settings.
- Redis is a cache, not the source of truth. Losing it only makes the next call
  setup rebuild from MariaDB.
- Back up TLS certificates, `.env` secrets and any carrier credentials.
- Keep the AGPL source and your deployment configuration under version control.
