# Console UI

The console is a Vue 3 application served at `/fs-switch`. It uses PrimeVue for
forms, tables and drawers, and Vue Flow for the dialplan canvas. The layout is a
four-part interface:

1. **Top bar** — the active Tenant selector, Socket.IO status, FreeSWITCH
   connection status and a manual live refresh.
2. **System tree** — the left sidebar. It is the anchor: Tenants, extensions,
   gateways, queues, dialplans and live views.
3. **Tabbed workspace** — the main panel. Selecting a tree item opens a
   workspace with tabs for settings, live status, table view, flow view and XML
   preview.
4. **Visual dialplan** — a Vue Flow canvas inside the dialplan workspace.
   Semantic flows use intent-level nodes with typed output ports; raw dialplans
   use FreeSWITCH application nodes. Clicking a node opens a PrimeVue property
   drawer.

## Navigation

```text
Overview
My extension
Tenants
Telephony
  Extensions
  DIDs
  Gateways
  Queues
  Dialplans
Live
  Channels
  Registrations
  Agents
  Wallboard
Settings
```

The tree is role-aware. A Tenant Admin sees Tenants, Telephony and Live but not
the global Settings page. A Supervisor sees Extensions and Live; an Agent sees
only Overview. System Manager sees everything. The tree is intentionally
shallow: a Tenant's context is shown on the dialplan and extension forms rather
than as a separate layer.

## Tenant selector

The top-bar selector changes the active Tenant. The choice is remembered in
`localStorage` and restored on the next visit if the user still belongs to that
Tenant. Switching Tenant reloads the bootstrap counts and the live snapshot;
realtime events for other Tenants are ignored.

New extensions, gateways, queues and Flows default to the active Tenant. The
Tenant field is disabled after creation. A Tenant's SIP domain and default
context are unique among enabled Tenants, and a Flow's context must match its
Tenant's default context. Document names are Tenant-qualified
(`accept-a::7101`); the displayed extension, queue, gateway and Flow title stay
natural and are unique inside the Tenant.

## Tenants panel

System Manager can create, edit and delete Tenants. A Tenant Admin can edit its
own Tenant and its membership rows, but cannot create or delete a Tenant. The
default Tenant cannot be disabled or deleted, because it is the fallback for
unknown routing labels. Membership roles are:

- **Admin** — read and write configuration, publish and roll back Flows.
- **Supervisor** — read configuration, run live actions and see live state.
- **Agent** — read only their own extension; the Telephony and Live trees are
  hidden.

Tenant fields also include an outbound caller ID fallback and a Tenant-specific
music-on-hold file. The call-setup document builders use those values before
the global Settings values.

The member list is a child table. Removing a user from a Tenant or disabling the
Tenant removes the projected `FS Switch *` role after commit.

## My extension

**My extension** shows the signed-in user's own endpoint for the active Tenant:
extension, display name, context, SIP domain and agent status. The owner can set
their own status to **Available**, **On Break** or **Logged Out**; the change is
persisted and sent to ESL. It also shows the WebRTC URL and the SIP password
behind a **Reveal** button. The endpoint returns credentials only to the
extension owner, and a user without an extension sees a clear empty state.

## DIDs workspace

The DIDs table is the Tenant's inbound-number inventory. Each row stores the
normalized carrier number, Tenant, enabled flag, an optional assigned Flow and a
description. An enabled DID assigned to a Published Flow compiles a public
transfer into that Tenant context; a DID without a Flow falls back to the Tenant
main inbound number. The Flow destination pattern still has to match the
carrier's number.

Tenant Admins can create, edit and delete DIDs. Supervisors get a read-only
view. DIDs are fixed to their Tenant after creation.

## Extension workspace

Tabs:

- **Details** — Tenant, extension, user, display name, SIP password, voicemail,
  caller ID and agent status. Leaving context blank uses the Tenant's default
  context.
- **Live** — registration state and active channels for this extension (future
  release).

The table shows Tenant, extension, display name, user, enabled and agent status.
Supervisors see the table read-only; Agents do not see the Telephony tree.

## Queue workspace

Tabs:

- **Details** — Tenant, queue name, strategy, max wait, music on hold, backup
  queue.
- **Agents** — the child table of extensions and levels. Every agent and backup
  queue must belong to the same Tenant.
- **Live** — queue depth, waiting callers and available agents (future release).

## Dialplan workspace

The dialplan list offers two creation paths:

- **New semantic flow** — the default, intent-level editor.
- **Raw dialplan** — the advanced FreeSWITCH application-chain editor.

Semantic flows open in `SemanticFlowEditor.vue`; raw flows keep the original
`FS Node` canvas. The list is filtered to the active Tenant and shows **Tenant**,
**Format** and **Publish** columns so an administrator can tell scope, graph
type and serving state apart before opening a document. The Publish column shows
`Draft` or `Published vN`. New Flows default to the active Tenant and its default
context.

The list actions publish a saved Draft and open the published-version history.
Rollback in that history repoints FreeSWITCH to an earlier Published version;
the Draft is not overwritten. The Diff action opens **Draft vs Published**:
settings, entry step, step and connection changes, and a unified XML diff. It is
read-only and available to any signed-in user who can read the Flow.

### Semantic flow editor

Tabs:

- **Flow** — Vue Flow canvas with a semantic palette and typed output ports.
  `menu` exposes one port per configured digit plus a `timeout` port; `time`
  exposes `match` and `no_match`. Drag from a port to connect steps. Click a
  step to open the property drawer.
- **Table** — the same steps and connections in editable grids, including the
  entry step and delete controls.
- **Simulate** — enter a destination, time and digits, then run the Draft
  through the route simulator. The result lists each step, the output port it
  took and a detail line; simulated steps are outlined on the Flow canvas.
  Editing the graph clears the result.
- **XML** — the draft compiled by the same compiler FreeSWITCH uses. This is a
  preview; the Published XML is what xml-curl serves. The preview works before
  the flow is saved.
- **Settings** — Tenant, context, extension name, destination pattern, priority,
  enabled flag and entry step. The context is fixed to the Tenant's default
  context.

Validation runs automatically while the flow changes and again before save.
Every non-terminal output must be connected. Saving is blocked until the flow
is valid. The entry extension matches the destination pattern and transfers
into the flow; the remaining steps compile to deterministic named extensions.
Saving stores the Draft; **Publish** compiles the saved Draft and makes it the
served version. The toolbar's **Draft vs Published** action opens the same
read-only diff as the list; it compares the saved Draft, so save first to include
canvas edits. The stored graph and publish lifecycle are documented in
[`flow-model.md`](flow-model.md).

### Raw flow editor

Tabs:

- **Flow** — Vue Flow canvas with a custom `FS Node`. Each node has a label,
  FreeSWITCH application and data/arguments.
- **Table** — the same nodes in order, with up/down controls.
- **XML** — the compiled extension, generated by the backend.
- **Settings** — Tenant, context, extension name, destination pattern, priority
  and enabled flag. The context is fixed to the Tenant's default context.

The raw canvas compiles a linear application chain. It is retained as an escape
hatch for senior engineers; it is not the default product model. Both editors
show the Draft/Published tag and a Publish action in the toolbar.

## Live views

- **Channels** — `show channels as json`, with hangup and transfer actions.
- **Registrations** — `show registrations as json`.
- **Agents** — `callcenter_config agent list`, with status changes.
- **Wallboard** - queue depth from active `callcenter` channels, configured
  waits, answered/abandoned counters, agent availability and active call paths.
  It refreshes the live snapshot every 10 seconds while open. A supervisor can
  **Listen**, **Whisper** or **Barge** from a call path; the action rings the
  supervisor's own extension and starts a FreeSWITCH eavesdrop leg.

The console takes one snapshot, then connects to the site's Socket.IO namespace
and applies `fs_switch_call`, `fs_switch_agent` and `fs_switch_registration`
events in place. Events carry the Tenant and are published only to that
Tenant's Admins/Supervisors and System Managers; the active Tenant's rows are
shown. While the socket is disconnected, the console polls every 30 seconds as a
fallback. The top bar shows whether the stream is **Live push**, **Connecting**
or **Polling fallback**.

A Supervisor or Tenant Admin can run live actions. The API checks the active
Tenant and the target channel or agent before it reaches ESL, so a supervisor in
one Tenant cannot act on another Tenant's rows. Agents do not see the Live tree.

## Visual language

The console follows the neutral language shared by Frappe CRM and Helpdesk. It
is quiet by default: light surfaces, thin borders, compact type and a dark ink
primary action. Colour is reserved for state.

- page canvas: `#f7f7f8`
- surfaces: `#ffffff`
- sidebar: `#fafafa`
- border: `#e5e5e5`
- ink: `#1f1f1f`
- muted text: `#6b6b6b`
- links and focus: `#2490ef`
- success: `#2f9e44`
- warning: `#b7791f`
- danger: `#d33b3b`
- radius: 8px for cards, 6px for controls
- tables: small-caps headers, 1px row rules, no zebra striping
- tags: compact pills with a tinted background

No gradients, dark chrome or decorative shadows. The PrimeVue preset in
`frontend/src/main.js` maps its primary palette to the dark ink action colour;
`frontend/src/styles.css` owns the console tokens and table, form and canvas
refinements.

The mark is a simple switch/route glyph, not a client logo. See
`apps/fs_switch/fs_switch/public/images/fs-switch-mark.svg`.
