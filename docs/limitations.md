---
title: "Alpha limitations"
space: "FS Switch"
---

FS Switch is an alpha control plane. The documentation describes the current
behaviour, including the places where the product is intentionally incomplete.
Read this page before a production rollout or a carrier migration.

For the development sequence, see [`roadmap.md`](roadmap.md). For live
acceptance gaps, see [`DEFERRED.md`](DEFERRED.md).

## Routing and DIDs

| Limitation | Current behaviour | What to do now |
|---|---|---|
| DIDs are inventory, not routes | The DID record stores a number, Tenant, enabled flag, optional Flow and description. The Flow destination pattern does the routing. | Align the DID and Flow pattern; test the exact carrier format. |
| Public context is main-DID only | A call entering `public` is transferred only for the global main DID, into the global default context. | Add a carrier/FreeSWITCH public-context route for other DIDs or send calls into the Tenant context directly. |
| No per-Tenant main DID | The main inbound number and default context are global settings. | Use a context-correct route per Tenant until per-Tenant inbound settings exist. |
| No DID starting node | The canvas does not start from a DID document. | Use the Flow destination pattern and the DID inventory together. |

## Carrier and gateways

| Limitation | Current behaviour | What to do now |
|---|---|---|
| Gateway record is not a live gateway | `FS Gateway` stores proxy, registration, credentials, context and codecs. It does not generate gateway XML or register to the carrier. | Create/configure the gateway in FreeSWITCH and keep its values aligned with the record. |
| Default gateway is metadata | The setting is stored but does not choose a gateway for a Flow. | Bridge through the configured FreeSWITCH gateway explicitly. |
| No carrier templates or failover | No SIP profile templates, ACL/TLS workflow, gateway ranking or failover. | Configure in FreeSWITCH and document the carrier's procedure. |
| No LCR or rate decks | No least-cost routing, effective dates, currency, rate import or route tester. | Treat as a separate subsystem. |

## Tenants and membership

| Limitation | Current behaviour | What to do now |
|---|---|---|
| Members must already exist | The member form validates an existing Frappe `User`; it does not create users or send invitations. | Invite/create the user in Desk first, then add the email and role. |
| Roles are projected after commit | The user may need to reload the console after a membership change. | Reload and verify the sidebar. |
| Roles are additive at the Frappe level | A user who is Admin in one Tenant and Agent in another keeps the Admin role globally; row hooks scope the rows. | Test the user against every Tenant they belong to. |
| Default Tenant fallback | Unknown routing labels fall back to the default Tenant. | Keep the default deliberate and do not use it as a security boundary. |
| No quotas or provisioning | No Tenant limits, automated provisioning, audit/reporting or tenant settings beyond the fields on the Tenant. | Manage manually for now. |

## Flows and media

| Limitation | Current behaviour | What to do now |
|---|---|---|
| Prompt is a FreeSWITCH path | The editor stores a playback path or stream URI; there is no upload, transcode or prompt library. | Use a prompt present in FreeSWITCH or a valid stream. |
| No holiday calendar node | Time conditions use a field and regex; no holiday calendar. | Use time conditions or an external schedule until the node exists. |
| No general collect-digits node | The IVR menu collects one digit; no arbitrary min/max digit collection. | Use separate menu steps or a raw application for now. |
| No webhook, TTS, ASR or AI node | The semantic palette stops at the current routing/media steps. | Use FreeSWITCH applications or external integrations. |
| No reusable subflows | Every Flow is a standalone graph. | Duplicate carefully or use a raw/transfer pattern. |
| Catch-all validation gap | The validator rejects many structural errors, but catch-all destination protection is not validated. | Review overlapping destination patterns and priority. |
| Simulator time limitations | Native FreeSWITCH `wday`, `hour` and `minute-of-day` fields are not evaluated by the simulator. | Use `${strftime(...)}` or a `set` variable for testable time conditions. |
| Loops have no automatic exit | A graph loop can run until a terminal step or hangup. | Add an explicit exit/timeout and lab-test it. |
| Published snapshot scope | Extension name and destination pattern are not duplicated into the published snapshot; the XML diff shows them. | Review the XML preview and diff before publishing. |

## Live operations

| Limitation | Current behaviour | What to do now |
|---|---|---|
| No in-console monitor audio | Listen/Whisper/Barge ring the supervisor's SIP endpoint; the browser console does not play the audio. | Use a registered softphone for the supervisor. |
| Wallboard is a live snapshot | It refreshes every 10 seconds and applies Socket.IO events; it is not a historical report. | Use CDR/BI when records exist. |
| No hold-time history | Longest current wait is shown; per-call hold history and per-agent daily metrics are missing. | Instrument FreeSWITCH/queue events and store them. |
| No call-path highlighting | The wallboard shows paths; the Flow canvas does not highlight a live path. | Use the wallboard and Channels. |
| Registration fan-out not fully verified | Local tests cover delivery, but multiple real Tenants and registration events still need a lab pass. | Run the acceptance matrix with real endpoints. |
| Simultaneous Tenant isolation not fully verified | API live-data isolation passed; Socket.IO recipient isolation under simultaneous calls still needs a real pass. | Run two calls/Tenants and inspect the socket recipients. |

## Endpoint and records

| Limitation | Current behaviour | What to do now |
|---|---|---|
| No embedded softphone | The console exposes credentials and a WebSocket URL; the phone is external. | Use a SIP/WebRTC client. |
| No presence or screen pop | Presence and screen pop are roadmap items. | Use the current live grids. |
| No CDR | Call detail records are not stored in Frappe. | Use FreeSWITCH CDR tooling or wait for the records slice. |
| No recording browser | Recording paths are configured; there is no browser, retention or consent workflow. | Manage recordings operationally. |
| No voicemail UI | A Flow can send a call to a voicemail mailbox; there is no mailbox browser. | Use FreeSWITCH voicemail tooling. |

## Platform and operations

| Limitation | Current behaviour | What to do now |
|---|---|---|
| MariaDB outage | A full database outage fails at Frappe HTTP middleware before XML-curl. Last-known-good helps a handler failure, not a dead database. | Use database HA and monitor the call-setup path. |
| Development server in Docker | The bundled stack runs Frappe's development web server and Socket.IO. | Use a production WSGI/reverse-proxy deployment for production. |
| Local TLS | The local FreeSWITCH certificate is self-signed, so `wss://` is not trusted. | Use `ws://` locally and a trusted certificate for `wss://`. |
| Open Desk | Desk can be mostly blank without a workspace; the console is the primary UI. | Use the console; configure Desk only when needed. |
| No HA or multi-node cache | The call-setup cache is Redis-backed but the deployment is not an HA design. | Plan Redis/Frappe/FreeSWITCH redundancy. |

## What "done" means

The alpha is useful for lab work, demos and controlled pilots. A production
release needs the P0/P1 items in [`roadmap.md`](roadmap.md), a real carrier
acceptance pass, a backup/restore rehearsal and a security review.
