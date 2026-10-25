# FS Switch documentation

FS Switch is an alpha-stage Frappe app and Vue console for operating
FreeSWITCH. Start with [`installation.md`](installation.md) and
[`first-steps.md`](first-steps.md) for the user-facing path. This page is the map
for the rest of the documentation.

## Start here

| Document | Read it when |
|---|---|
| [`installation.md`](installation.md) | You are installing FS Switch with Docker or on an existing Frappe bench. |
| [`first-steps.md`](first-steps.md) | You have a running console and want to create an extension, Flow and first test call. |
| [`../README.md`](../README.md) | You want the feature overview, quick start or project links. |
| [`PRODUCT.md`](PRODUCT.md) | You need the product direction, personas and scope. |
| [`STATUS.md`](STATUS.md) | You need the current build status against the original source documents. |
| [`ACCEPTANCE.md`](ACCEPTANCE.md) | You are running the first live bench, permission, Socket.IO or XML-curl acceptance pass. |

## User guide

| Document | Read it when |
|---|---|
| [`tenants.md`](tenants.md) | You are creating a Tenant, adding members or switching Tenant scope. |
| [`extensions.md`](extensions.md) | You are creating an endpoint, SIP password or agent status. |
| [`queues.md`](queues.md) | You are configuring a queue, agents, tiers, hold music or wait time. |
| [`dids.md`](dids.md) | You are adding inbound numbers and aligning Flow destination patterns. |
| [`gateways.md`](gateways.md) | You are preparing a carrier trunk and its FS Gateway record. |
| [`flows.md`](flows.md) | You are building, simulating, publishing or rolling back a Flow. |
| [`live-operations.md`](live-operations.md) | You are using Channels, Registrations, Agents, the wallboard or monitoring. |
| [`settings.md`](settings.md) | You are changing XML-curl, ESL, media, recording or global routing settings. |
| [`troubleshooting.md`](troubleshooting.md) | You need a layer-by-layer diagnosis before changing configuration. |

## Reference and operations

| Document | Read it when |
|---|---|
| [`architecture.md`](architecture.md) | You need the control-plane/data-plane boundaries, cache or live-event design. |
| [`flow-model.md`](flow-model.md) | You are changing the Flow graph, node registry, compiler, simulator, publish lifecycle or diff. |
| [`ui.md`](ui.md) | You are changing the console layout, semantic canvas, live views or publish/diff UI. |
| [`operations.md`](operations.md) | You are running, publishing, troubleshooting or backing up a deployment. |
| [`development.md`](development.md) | You are setting up a bench, running tests or building the console. |
| [`DEFERRED.md`](DEFERRED.md) | You need the current limitations, blocked validation and next slices. |

## Operating FS Switch

The root README covers Docker and existing-bench installation. In day-to-day
operation:

1. Create or edit Tenants, DIDs, Flows, extensions, queues and gateways in
   Frappe or the console. Tenant membership controls who can see and change
   them.
2. Validate the Flow. The semantic editor blocks save until every non-terminal
   output is connected.
3. Publish. XML-curl serves only the Published version; saving a Draft does not
   change live routing.
4. Use **Draft vs Published** in the Dialplans list or the semantic editor
   toolbar before publishing.
5. Roll back by repointing the Published version. The Draft is preserved.
6. Watch the ESL listener for live call, agent and registration events. The
   console applies Socket.IO events in place and polls every 30 seconds only
   while the socket is disconnected.

The call-setup path is cached in Redis. Publish, rollback, enable/disable,
settings, Tenant, extension, queue and gateway changes invalidate the current
cache after commit. Last-known-good XML survives invalidation and is served when
a rebuild fails.

## Architecture decisions

- [ADR 0001: Frappe as the control plane](adr/0001-frappe-control-plane.md)
- [ADR 0002: Semantic Flow graph](adr/0002-semantic-flow-graph.md)
- [ADR 0003: Call-setup path cache](adr/0003-call-setup-path-cache.md)

## Source material

The research notes are retained for context. They are not normative:

- [`product-thesis.txt`](product-thesis.txt)
- [`FreeSWITCH UI.txt`](FreeSWITCH%20UI.txt)
- [`research-stack-and-ui-model.txt`](research-stack-and-ui-model.txt)
- [`research-world-class-ui-layout.txt`](research-world-class-ui-layout.txt)

## Documentation rule

Every user-visible behaviour change updates the README or the relevant document
in the same pull request. Every architectural change adds or updates an ADR.
Deferred work goes to [`DEFERRED.md`](DEFERRED.md), not into a comment in code.
