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

The default Tenant is cached in Redis so a warm call setup does not read MariaDB
for tenant resolution.

## ESL listener

The listener subscribes to channel and call-center events and publishes them on
Frappe's realtime channel. The console currently polls live state every five
seconds; socket subscription is deferred.

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
| Live state is stale | Is the ESL listener running? The console falls back to polling every five seconds. |
| Publish fails | Read the validation error. The compiler rejects broken routes before version history or serving changes. |
| Publish succeeded but XML-curl is stale | Check the Redis connection, the cache key Tenant/context, and FreeSWITCH's `reloadxml`. |
| MariaDB outage breaks call setup | Confirm Redis is up, the secret hash is cached and a last-known-good document exists. |

## Backup and recovery

- Back up MariaDB. It holds Flows, versions, extensions, queues, gateways and
  settings.
- Redis is a cache, not the source of truth. Losing it only makes the next call
  setup rebuild from MariaDB.
- Back up TLS certificates, `.env` secrets and any carrier credentials.
- Keep the AGPL source and your deployment configuration under version control.
