---
title: "Roadmap and feature status"
space: "FS Switch"
---

This page is the user-facing map of what is shipped, what is partial and what is
still to build. It is checked against [`PRODUCT.md`](PRODUCT.md),
[`product-thesis.txt`](product-thesis.txt), [`STATUS.md`](STATUS.md) and the
current console.

**Status legend**

- **Shipped** - implemented and covered by tests/build; live use still depends on
  the deployment.
- **Partial** - the core exists, but an important production path is missing.
- **Next** - the next development slice.
- **Not started** - design or implementation has not begun.

## Current status

| Area | Status | What exists | What is missing |
|---|---|---|---|
| **Frappe control plane** | Shipped | DocTypes, roles, audit, REST, Tenant scope, XML-curl, ESL. | More operational observability and HA. |
| **Semantic Flow core** | Shipped | Schema, node registry, validation, compiler, simulator, Draft/Published, diff, rollback. | Catch-all validation; richer node library. |
| **Publishing and call-setup cache** | Shipped | Immutable versions, Redis current/last-known-good, after-commit invalidation. | Surviving a full MariaDB outage. |
| **Tenant layer** | Partial | Tenants, SIP domains, contexts, membership, roles, unique names, selector. | Invite workflow, quotas, tenant settings/provisioning, audit/reporting. |
| **Extensions and registrations** | Partial | Directory, passwords, agent status, My extension, WebRTC seed. | Embedded softphone, presence, screen pop, credential lifecycle UX. |
| **Queues and call center** | Partial | Queues, tiers, strategies, backup queues, wallboard, agent status. | Hold history, per-agent metrics, queue events, wrap-up. |
| **Live operations** | Partial | Channels, registrations, agents, wallboard, hangup/transfer, monitor actions. | In-console audio, call-path highlighting, real-time queue metrics. |
| **Carrier layer** | Partial | FS Gateway CRUD with proxy, registration, credentials, codecs. | Gateway XML generation, templates, failover, ACL/TLS UI, LCR. |
| **DIDs and inbound routing** | Partial | Tenant DID inventory, normalization, public DID routes, Tenant main-number fallback. | Real carrier acceptance, unknown-DID policy, multi-Tenant live test. |
| **Media and prompts** | Partial | Prompt paths, MOH, recording path settings. | Upload, transcoding, prompt versioning, media browser, retention. |
| **Records and voicemail** | Partial | Voicemail/record nodes and storage settings. | CDR, recording browser, voicemail box UI, consent/retention. |
| **Logic extensions** | Partial | IVR menu, time, ring group, queue, voicemail, transfer, conference, park, set, sleep, record, hangup. | Holiday calendar, collect-digits, webhook, TTS/ASR, AI agents, subflows. |
| **LCR and rate decks** | Not started | None. | Carriers, rates, effective dates, ranking, failover, route tester. |
| **Realtime** | Partial | Socket.IO call/agent/registration events, polling fallback. | Real recipient isolation with simultaneous Tenants and registration fan-out. |

## What is left to develop

### P0 - make live inbound routing correct

1. **Public DID acceptance.**
   Per-DID public routing and Tenant main-number fallback are implemented and
   covered by XML tests. Validate a real carrier call for two DIDs in two
   Tenants, plus/no-plus variants, an unpublished Flow and a disabled DID.

2. **Unknown-DID policy.**
   Decide whether an unknown number should fail closed or use the global
   main-DID fallback. Record the decision in the routing tests and docs.

3. **Gateway generation.**
   `FS Gateway` records are inventory only. Generate the matching FreeSWITCH
   gateway XML (or a controlled configuration fragment), including
   registration, proxy, realm, from-domain, caller ID, codecs and inbound
   context. Keep credentials out of logs.

4. **Carrier acceptance.**
   Test a real trunk registration, inbound DID, outbound call, caller ID,
   failover and a two-Tenant call with a real carrier.

### P1 - complete the operating product

5. **Live Tenant isolation.**
   Run simultaneous calls in two Tenants and verify Socket.IO recipient
   isolation, registration event fan-out and cross-Tenant action denial.

6. **Embedded softphone and monitor audio.**
   Add the reusable SIP.js/JsSIP component with WSS/STUN/TURN, presence, screen
   pop and call controls. Use it for supervisor Listen/Whisper/Barge instead of
   requiring a separate softphone.

7. **Call records and recordings.**
   Add CDR ingestion, recording metadata/browser, voicemail box UI and
   retention/consent policy. Keep recordings out of Frappe's primary database.

8. **Queue history.**
   Persist queue join/answer/abandon and hold time, and produce per-agent daily
   metrics. The current wallboard is a live projection only.

9. **Media manager.**
   Upload, validate, transcode and version prompts; add a prompt picker and
   default IVR/MOH selection per Tenant.

10. **Logic depth.**
    Add holiday calendars, general collect-digits, webhooks, TTS/ASR adapters,
    AI-agent nodes, reusable subflows and call screening.

11. **Tenant operations.**
    Add quotas, recording/voicemail defaults, provisioning, audit/reporting and
    a real invite flow. The current member form only accepts existing Frappe
    users.

12. **Carrier routing depth.**
    Add carrier templates, failover ranking, ACL/TLS workflows, LCR, rate decks,
    effective dates and a route tester.

13. **Reliability and observability.**
    Address the MariaDB middleware failure, add XML-curl/cache metrics and
    traceable publish/reload history, and make the Open Desk landing useful.

## Documentation coverage

The current documentation covers the shipped and partial paths:

| Page | Covers | Known boundary |
|---|---|---|
| [`installation.md`](installation.md) | Docker and existing-bench install, ports, upgrades, security. | FreeSWITCH compile time; no managed hosting. |
| [`first-steps.md`](first-steps.md) | Extension, queue, Flow, publish, test call, carrier preparation. | Uses a softphone; no embedded phone. |
| [`tenants.md`](tenants.md) | Tenant fields, roles, members, switching, isolation. | Members must exist as Frappe users. |
| [`extensions.md`](extensions.md) | SIP endpoint, password, caller ID, agent status, WebRTC. | No embedded softphone. |
| [`queues.md`](queues.md) | Strategies, agents, tiers, backup queues, live metrics. | No historical reporting. |
| [`dids.md`](dids.md) | Inventory, normalization, Flow regex alignment, public DID routes and Tenant fallback. | Real carrier acceptance remains. |
| [`gateways.md`](gateways.md) | Gateway fields, trunk hand-off, verification. | Record does not generate FreeSWITCH config. |
| [`flows.md`](flows.md) | Nodes, ports, validation, simulator, XML, publish, rollback. | No media manager; catch-all validation gap. |
| [`live-operations.md`](live-operations.md) | Channels, registrations, agents, wallboard, monitoring. | No in-console audio; live history limited. |
| [`settings.md`](settings.md) | XML-curl, ESL, global main DID/default context, media, recording. | Global fallback is separate from Tenant main numbers. |
| [`troubleshooting.md`](troubleshooting.md) | Layer-by-layer diagnosis and useful commands. | Not a substitute for FreeSWITCH/carrier logs. |
| [`limitations.md`](limitations.md) | Consolidated alpha limitations and workarounds. | Read before production. |
| [`recipes.md`](recipes.md) | Menu, after-hours, queue and DID examples. | Holiday/subflow nodes are not implemented. |

### Documentation still worth adding

- A **carrier-specific setup guide** once gateway generation exists.
- An **API/softphone integration reference** for `get_softphone_config` and the
  future embedded widget.
- A **CDR/recording/voicemail data model** once those features exist.
- A **migration and rollback runbook** with real versioned releases.
- A **permission test matrix** with real users for all three roles.

## Release gates

Before calling the product production-ready:

- [ ] Per-DID and per-Tenant public routing tested with two carriers/Tenants.
- [ ] FS Gateway to FreeSWITCH gateway generation tested with registration and
      failover.
- [ ] Simultaneous Tenant calls and Socket.IO recipient isolation tested.
- [ ] A real carrier inbound/outbound call with audio and caller ID.
- [ ] CDR/recording/voicemail retention and consent decisions made.
- [ ] MariaDB/cache failure behaviour tested.
- [ ] Backup, restore and upgrade rehearsed.
- [ ] Security review of XML-curl, ESL, SIP, RTP and tenant boundaries.

## Related documents

- [`STATUS.md`](STATUS.md) - implementation status against the source material
- [`DEFERRED.md`](DEFERRED.md) - intentionally deferred work
- [`ACCEPTANCE.md`](ACCEPTANCE.md) - live acceptance checklist
- [`limitations.md`](limitations.md) - consolidated alpha limitations
- [`PRODUCT.md`](PRODUCT.md) - product direction and pillars
