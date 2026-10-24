# Live bench acceptance

This is the checklist for the first real-site acceptance run. It is deliberately
manual: a passing unit test does not prove Frappe permissions, Socket.IO
authentication, XML-curl or FreeSWITCH routing.

## 1. Start the stack

```bash
cp .env.example .env
# set every CHANGE_ME value and a unique FS_SWITCH_XML_CURL_SECRET
docker compose up -d --build
docker compose ps
```

Wait until the Frappe health check passes. For a local Docker site:

```text
http://fs-switch.localhost:8000/fs-switch
```

## 2. Migrate and create the schema

```bash
docker compose exec frappe bench --site fs-switch.localhost migrate
docker compose exec frappe bench --site fs-switch.localhost execute fs_switch.tenants.after_migrate
```

Confirm:

- `FS Tenant`, `FS Tenant Member`, `FS DID` exist.
- `FS Switch Admin`, `FS Switch Supervisor` and `FS Switch Agent` exist.
- The default Tenant exists and is enabled.
- `FS DID` is listed in the console’s Telephony tree.
- Existing Flows have a `tenant` and `published_tenant`.

## 3. Roles and membership

Create three users in Desk or the console, for example:

```text
tenant-admin@example.com
tenant-supervisor@example.com
tenant-agent@example.com
```

Add them to a Tenant with roles `Admin`, `Supervisor` and `Agent`. Confirm:

- The Admin can edit the Tenant, create DIDs/extensions/flows and publish.
- The Supervisor can read Extensions/DIDs and use Live, but cannot edit config.
- The Agent sees `My extension` and Overview, but not Telephony or Live.
- System Manager sees every Tenant and can switch between them.
- Removing a membership removes the projected `FS Switch *` role after commit.
- The default Tenant cannot be disabled or deleted.

The idempotent fixture creates acceptance Tenants, users, extensions, a queue,
two Flows and two DIDs, then checks role projection, row isolation, DID
normalization, publishing and the call-setup handlers. Fixtures use the
`accept-*` prefix and can be removed after the run:

```bash
docker compose exec -T frappe bash -lc \
  'cd /home/frappe/fs-switch-bench && bench --site fs-switch.localhost console < /home/frappe/fs-switch/scripts/live_acceptance.py'
```

Useful console checks:

```python
frappe.get_roles("tenant-admin@example.com")
frappe.get_all("FS Tenant Member", fields=["parent", "user", "role", "enabled"])
frappe.get_all("FS Extension", filters={"tenant": "default"}, fields=["name", "user"])
```

## 4. Row-level isolation

Create two Tenants and one document in each. Then check:

- Tenant A’s Admin cannot list or read Tenant B’s Flows, DIDs, extensions,
  gateways or queues.
- A Supervisor in A cannot run a live action against B’s channel or agent.
- An Agent can read only their own extension.
- A user with no membership gets no Tenant data.
- A normal save cannot move a document to another Tenant.
- A normal save cannot change `published_*` fields or version history.

## 5. DID inventory

Create a DID in the active Tenant:

- `+1 (415) 555-0100` normalizes to `+14155550100`.
- `14155550100` is rejected as a duplicate.
- Assigning a Flow from another Tenant is rejected.
- The DID cannot be created without a Tenant or number.
- A Supervisor sees DIDs read-only.

## 6. XML-curl

Use the secret from `.env`:

```bash
curl -sS "http://localhost:8000/api/method/fs_switch.api.xml_curl?secret=$SECRET&section=directory&domain=localhost"
curl -sS "http://localhost:8000/api/method/fs_switch.api.xml_curl?secret=$SECRET&section=dialplan&context=default"
curl -sS "http://localhost:8000/api/method/fs_switch.api.xml_curl?secret=$SECRET&section=configuration&key_value=callcenter.conf"
```

Confirm:

- A missing or wrong secret returns `Forbidden`.
- Directory contains the Tenant’s extensions.
- Dialplan contains only Published Flows for the resolved Tenant.
- `callcenter.conf` contains every enabled Tenant’s queues and agents.
- A cold cache builds and caches the document.
- A warm cache returns the same document without a rebuild.
- With MariaDB stopped, record whether the request reaches the handler. In the
  current Frappe stack it fails at HTTP middleware before the cache is read;
  this is a known limitation, not a handler-cache failure.
- A wrong context/domain falls back to the configured default Tenant.

Inspect cache keys:

```bash
docker compose exec redis-cache redis-cli --scan --pattern 'fs_switch:xml:*'
```

## 7. Publish and rollback

1. Create a semantic Flow with a menu and at least one branch.
2. Save the Draft and run the route simulator.
3. Publish it; verify a version row is created and `reloadxml` is reported.
4. Edit the Draft; verify `publish_status` becomes `Draft`.
5. Roll back; verify the Published pointer moves and the Draft survives.
6. Confirm XML-curl still serves only the Published XML.

## 8. Socket.IO

Log in as an Admin/Supervisor in a browser.

- The top bar goes from **Connecting** to **Live push**.
- The browser network tab shows a WebSocket connection to port 9000 (or the
  configured `fs_switch_socketio_url`).
- Channel, agent and registration events update without a page refresh.
- If Socket.IO is blocked, the console shows **Polling fallback** and live grids
  still refresh.
- An Agent does not receive live events.

## 9. Live actions and realtime isolation

With a test call or a simulated ESL event:

- Hangup and transfer work against the active Tenant.
- Agent status changes from the supervisor table and from **My extension**.
- A Supervisor in Tenant A cannot act on Tenant B’s rows.
- Realtime recipients are limited to the owning Tenant’s Admins/Supervisors
  plus System Managers.

## 10. FreeSWITCH lab

- Register a WebRTC extension with the values from **My extension**.
- Call the main DID and walk a menu, timeout and transfer.
- Verify a queue call reaches an available agent.
- Verify a disabled Flow is not served.
- Verify a Tenant domain/context routes to the right directory and dialplan.
- Verify `reloadxml` after publish and rollback.
- Record any XML or ESL error from `docker compose logs freeswitch`.

## 11. Recorded result

The local Docker run on 2026-10-23 passed migration, role creation, membership
projection, Tenant row isolation, DID creation, publishing, HTTP XML-curl with
cold and warm cache, wrong-secret rejection, Socket.IO auth/delivery, ESL live
data, agent status changes, and a loopback call event delivered from the ESL
listener through Frappe realtime to Socket.IO. The authenticated `/fs-switch`
page and built `app.js` were also served with HTTP 200.

The console page initially returned 500 because Frappe expects the controller
for `fs-switch.html` at `www/fs_switch.py`, not `www/fs-switch.py`. Renaming the
controller fixed the page.

Login from `/login` now lands on `/fs-switch` instead of the blank Desk
Framework page. The site home page and the three FS Switch roles point at the
console; Desk remains available through **Open Desk**.

Browser QA with the local Chromium session also passed:

- Admin Overview showed **Live push**, **FreeSWITCH connected**, Tenant selector
  and live counts.
- Tenant switching from Default to Acceptance A updated DIDs and live data.
- Tenants panel showed all Tenants with the default row protected from delete.
- Dialplans list showed the acceptance Flow as **Published v3**.
- Live Agents showed `7101@accept_a` with `Available`/`Waiting`.
- Supervisor status change from the Agents table passed.
- Agent navigation showed only Overview and My extension; My extension showed
  the extension, context, SIP domain, password reveal and status control.
- Agent, Supervisor and Admin role-aware navigation matched the intended model.

Deep interaction QA on a seeded semantic Flow also passed:

- The canvas rendered the entry badge, four steps, digit/timeout ports and all
  four edges.
- The property drawer edited a menu prompt and added a digit option; the new
  port appeared and validation blocked Save until it was connected.
- The route simulator returned the full Answer → Menu → Play → Hangup path,
  highlighted the steps, showed variables, survived the validation pass and
  cleared after a genuine graph edit.
- Save, publish, double-click publish, XML preview, Draft vs Published, version
  history and rollback behaved correctly; XML stayed read-only.
- Long/XSS-like prompt text rendered as text and created no element or alert.
- Version and diff drawers fit 375px and 768px viewports without document
  overflow.
- Escape returned keyboard focus to the version/diff trigger.
- Axe reported zero critical or serious violations on the dialplan list,
  semantic editor, property drawer, version drawer and diff drawer. Empty table
  headers remain a minor warning.
- A synthetic palette-to-canvas drag could not be automated reliably; a real
  handle drag from a dynamic menu port to another node did connect, and the
  validation state cleared.

Supervisor users have no Dialplans entry in the current role model, so the
read-only semantic editor was not part of the Supervisor pass.

Tenant uniqueness and wallboard checks also passed:

- The migration renamed extensions, queues, gateways and Flows to
  Tenant-qualified document names while preserving their natural key fields and
  link references.
- Creating `7101` twice in Acceptance A is rejected; creating `7101` in
  Acceptance B succeeds.
- The directory user remains `7101` in Acceptance A and the callcenter tier is
  `7101@accept_a`, not the scoped document name.
- The Wallboard shows queue depth, configured wait, answer/abandon counters,
  available/busy agents and active call paths for the active Tenant.
- The live snapshot derives queue depth from active callcenter channels and
  returns a zeroed wallboard summary when FreeSWITCH has no calls.

Real WebRTC call lab on 2026-10-24:

- Extension `7101` registered with the `webrtc` profile over
  `ws://localhost:5066` using its own `get_softphone_config` credentials.
- A call from the browser to the QA menu (`9300`) reached the timeout branch;
  `fs_switch_flow`, `lab_stage` and `lab_route` persisted on the channel.
- A second menu call accepted SIP INFO digit `1`; `menu_digit=1` and
  `lab_route=digit1` proved the digit branch.
- A two-node `set` loop executed repeated XML transfers until termination.
- A call to the QA queue (`9400`) bridged to the registered agent. FreeSWITCH
  showed the caller and agent legs, and the wallboard reported one active call,
  one answered call and the queue call path.
- The missing `Caller-Context` XML-curl field was fixed; WebRTC calls now select
  the Tenant by the authenticated user's context.
- Local WebRTC media required `apply-candidate-acl = rfc1918.auto`; without it,
  FreeSWITCH dropped the browser's RFC1918 ICE candidates.
- The `webrtc` profile uses INFO DTMF with liberal DTMF enabled.

Multi-Tenant and supervisor monitoring:

- Acceptance B queue `accept_support_b` bridged a real WebRTC call from
  extension `7201`; Acceptance A live data stayed empty while the B call was
  active.
- The wallboard rendered Listen, Whisper and Barge actions for the active call.
- Each action originated the supervisor extension `7102`; the resulting channel
  ran `eavesdrop`. Whisper set `eavesdrop_whisper_bleg=true`; Barge set both
  aleg and bleg whisper flags.
- The wallboard UI showed the monitor actions with a valid Frappe CSRF token.
  Actual in-console audio playback is still pending because the console has no
  embedded softphone yet.

One check did not pass: stopping MariaDB makes HTTP XML-curl return 500 before
the handler runs because Frappe’s request middleware needs the database. The
handler-level cache and secret hash are still useful, but they are not a full
database-outage workaround.

## 12. Evidence

Record the commit, Docker image IDs, command output and screenshots. Update
[`STATUS.md`](STATUS.md) and [`DEFERRED.md`](DEFERRED.md) with what passed and
what remains blocked.
