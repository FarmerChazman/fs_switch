---
title: "Troubleshooting"
space: "FS Switch"
---

Start with the layer where the failure happens: browser, Frappe, FreeSWITCH,
SIP/media, or carrier. Do not change several layers at once.

## First checks

```bash
docker compose ps
docker compose logs -f frappe
docker compose logs -f freeswitch
curl -fsS http://fs-switch.localhost:8000/api/method/ping
```

The console top bar should show **FreeSWITCH connected** and **Live push**. If
either is missing, fix that before debugging call routing.

## Console and login

| Symptom | Check |
|---|---|
| `/fs-switch` redirects to login | Expected when there is no session. Log in with a Frappe user. |
| Console page is blank | Check `/assets/fs_switch/console/index.html` and `assets/app.js` return 200; rebuild the console. |
| No sidebar items | The user has no enabled Tenant membership; check **Tenants → Members** and reload. |
| Agent sees Telephony/Live | Check the Tenant role projection; an Agent should only see Overview and My extension. |
| `Open Desk` is blank | The Desk workspace is a separate Frappe surface; the console does not depend on it. |

## FreeSWITCH connection

| Symptom | Check |
|---|---|
| Top bar says not connected | ESL host/port/password, event-socket ACL, container network. |
| XML-curl 401/403 | The shared secret in `xml_curl.conf.xml` and **Settings** must match. |
| XML-curl 500 | Frappe HTTP middleware or database; inspect the Frappe log. |
| XML-curl returns `not found` | No Published, enabled Flow for the Tenant/context, or no last-known-good cache. |
| ESL listener log empty | Check the entrypoint/service and the `bench execute fs_switch.esl_listener.run` process. |

Useful commands inside the FreeSWITCH container:

```bash
fs_cli -x "status"
fs_cli -x "show channels"
fs_cli -x "show registrations"
fs_cli -x "sofia status"
fs_cli -x "reloadxml"
```

## Softphone registration

| Symptom | Check |
|---|---|
| `NotAllowedError` from the browser | Grant microphone/camera permission or launch the browser with test media flags. |
| Register fails | Extension enabled, SIP password, SIP domain, WebSocket URL (`ws://localhost:5066` locally). |
| WebSocket connection fails | Port 5066 reachable, `webrtc` profile running, reverse proxy allows WebSocket upgrade. |
| Registration succeeds but no audio | RTP range, `public_ip`, firewall/NAT, ICE candidates and codecs. |
| `wss://` fails locally | The local certificate is self-signed. Use `ws://` for the lab or install a trusted certificate. |

## Inbound calls and DIDs

| Symptom | Check |
|---|---|
| Call reaches FreeSWITCH but no Flow | Destination pattern, Tenant context, Published state, priority. |
| Main DID works, another DID does not | Only the main DID is forwarded from the `public` context in this alpha. Add a public-context route or send the call into the Tenant context. |
| A second Tenant's DID goes to the default Tenant | The shared public path uses the global main DID and default context; route the call with the correct Tenant context. |
| DID record has the right Flow but calls fail | The Assigned Flow is informational. The Flow destination pattern does the routing. |
| Flow simulator matches but carrier does not | Compare the exact carrier number, including `+`, country code and prefix. |

## Queues and agents

| Symptom | Check |
|---|---|
| Queue not visible in FreeSWITCH | Queue enabled, `callcenter.conf` loaded, `callcenter_config queue list`. |
| Agent not ringing | Extension enabled/registered, agent Available, membership and tier loaded. |
| Queue depth stays zero | Call is in the queue context and an active `callcenter` channel exists. |
| Agent status change does not stick | Check the extension owner/membership and the ESL reply; inspect `callcenter_config agent list`. |
| Wallboard has stale counters | Snapshot/polling or FreeSWITCH queue state; refresh and check the live socket. |

## Flows and publishing

| Symptom | Check |
|---|---|
| Save blocked | Connect all non-terminal outputs, fill required fields, remove unreachable nodes. |
| Draft looks right but calls use old XML | Publish. XML-curl serves only Published XML. |
| Publish reports reload failure | Run `reloadxml`; verify XML-curl and the Flow status. |
| Rollback did not change routing | Rollback repoints the Published version; verify the cache and reload. |
| Prompt missing | The playback path must exist in FreeSWITCH or be a stream URI. |
| Queue/voicemail node fails | The target queue/mailbox must exist in the active FreeSWITCH configuration. |

## Realtime

| Symptom | Check |
|---|---|
| Live push never connects | Socket.IO port 9000, site name, reverse proxy, browser console. |
| Polling fallback works but push does not | Frappe realtime/socketio process and the namespace. |
| Another Tenant's events appear | Check Tenant filtering and the selected Tenant; this is a security issue, report it. |

## Database outage

A warm XML-curl cache protects an executing request from a compiler/lookup
failure, but a full MariaDB outage still fails at Frappe HTTP middleware before
the handler runs. Do not treat last-known-good XML as a database-outage
workaround. Keep the database highly available if call setup must survive a
database failure.

## Useful implementation references

- [`operations.md`](operations.md) - cache, ESL listener, publish/rollback and runtime checks.
- [`flow-model.md`](flow-model.md) - graph, compiler and publish lifecycle.
- [`development.md`](development.md) - bench, tests, frontend build and Docker.
- [`ACCEPTANCE.md`](ACCEPTANCE.md) - live acceptance checks and known gaps.
