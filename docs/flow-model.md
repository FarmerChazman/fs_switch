# Semantic flow model

This document is the reference for the `semantic` graph format in
`FS Dialplan` and the compiler in `apps/fs_switch/fs_switch/flow.py`.

It is intentionally narrower than the long-term product vision. It defines the
v1 contract that the canvas, property drawer and compiler must share.

## 1. Stored document

A semantic flow is stored in `FS Dialplan.graph` with
`FS Dialplan.graph_format = semantic`.

```json
{
  "schema": 1,
  "entry": "answer",
  "nodes": [
    { "id": "answer", "type": "answer", "data": {} },
    {
      "id": "menu",
      "type": "menu",
      "data": {
        "prompt": "ivr/main_menu.wav",
        "variable": "menu_digit",
        "options": [
          { "digit": "1", "label": "Sales" },
          { "digit": "2", "label": "Support" }
        ]
      }
    },
    { "id": "sales", "type": "queue", "data": { "queue": "sales" } },
    { "id": "support", "type": "voicemail", "data": { "mailbox": "support" } },
    { "id": "closed", "type": "hangup", "data": {} }
  ],
  "edges": [
    { "id": "e1", "source": "answer", "target": "menu", "sourceHandle": "next" },
    { "id": "e2", "source": "menu", "target": "sales", "sourceHandle": "digit:1" },
    { "id": "e3", "source": "menu", "target": "support", "sourceHandle": "digit:2" },
    { "id": "e4", "source": "menu", "target": "closed", "sourceHandle": "timeout" },
    { "id": "e5", "source": "sales", "target": "closed", "sourceHandle": "next" }
  ]
}
```

`position` and other Vue Flow fields are allowed and ignored by the compiler.
`entry` names the first node. Every node must be reachable from `entry`.

## 2. Node contract

A node has:

```json
{
  "id": "menu",
  "type": "menu",
  "data": {},
  "position": { "x": 0, "y": 0 }
}
```

- `id` is unique within the flow.
- `type` selects a registry entry.
- `data` is node-specific and must contain the required fields.
- `position` is UI state and has no runtime meaning.

## 3. v1 node catalog

| Type | Purpose | Outputs | Required data |
|---|---|---|---|
| `answer` | Answer the call | `next` | - |
| `play` | Play a prompt | `next` | `prompt` |
| `menu` | Play a prompt, collect a digit and branch | `digit:<digit>` for each option, `timeout` | `prompt`, `options` |
| `time` | Branch on a FreeSWITCH condition field | `match`, `no_match` | `expression` |
| `ring_group` | Bridge a caller to one or more endpoints | `next` | `endpoints` |
| `queue` | Enter a `mod_callcenter` queue | `next` | `queue` |
| `voicemail` | Deliver the call to a mailbox | terminal | `mailbox` |
| `transfer` | Blind-transfer to a destination | terminal | `destination` |
| `conference` | Join a conference room | terminal | `room` |
| `park` | Park the call | terminal | - |
| `hangup` | Hang up, optionally with a cause | terminal | - |
| `set` | Set a channel variable | `next` | `variable` |
| `sleep` | Pause the call | `next` | - |
| `record` | Start a session recording | `next` | `path` |

The machine-readable palette is exposed by
`fs_switch.api.get_flow_catalog`.

### `menu`

`menu` compiles to:

1. `set <variable>=` to clear stale digits;
2. `play_and_get_digits` with the configured prompt, invalid prompt, variable
   and a digit regexp derived from the options;
3. a transfer to a branch selector extension;
4. one selector extension per digit and one for timeout.

Example data:

```json
{
  "prompt": "ivr/main_menu.wav",
  "invalid_prompt": "ivr/ivr-that_was_an_invalid_entry.wav",
  "variable": "menu_digit",
  "min_digits": 1,
  "max_digits": 1,
  "tries": 1,
  "timeout_ms": 5000,
  "terminators": "#",
  "options": [
    { "digit": "1", "label": "Sales" },
    { "digit": "2", "label": "Support" }
  ]
}
```

The timeout branch uses the empty value (`^$`). If the caller enters a digit
that is not an option, `play_and_get_digits` plays the invalid prompt and
retries; after the configured tries, the variable is empty and the timeout edge
is used. Digit-branch menus are single-digit selectors, so `min_digits` and
`max_digits` must both be `1`.

### `time`

`time` compiles to a selector with two branch extensions on the same field:

- `match`: the configured expression;
- `no_match`: `^.*$`.

The first selector that matches transfers to its target. `field` defaults to
`${strftime(%H%M)}`; set it to a FreeSWITCH condition field such as `wday`,
`hour` or `minute-of-day` when using native time ranges.

### `ring_group`

`endpoints` is a list. A bare extension is converted to
`user/<extension>@${domain_name}`. A full dial string containing `/` is used
as-is. Endpoints are joined with `,` (simultaneous ring). `timeout_seconds`
defaults to 30 and adds a global `{leg_timeout=...}` prefix; set it to `0` to
omit the prefix.

### `queue`

A bare queue name is scoped to the flow context:
`support` becomes `support@default`. A value that already contains `@` is used
as-is.

### `voicemail`

Compiles to `voicemail <profile> <domain> <mailbox>`, with defaults
`profile=default` and `domain=${domain_name}`.

### `transfer`

Compiles to `transfer <destination> <dialplan> <context>`, with defaults
`dialplan=XML` and the flow context.

## 4. Edge handles

`sourceHandle` is the output port. It is optional for single-output nodes and
defaults to `next`.

| Handle | Used by | Meaning |
|---|---|---|
| `next` | linear nodes | Continue to the next node |
| `digit:0` ... `digit:9` | menu | The caller selected that digit |
| `timeout` | menu | No valid digit was collected |
| `match` | time | The condition matched |
| `no_match` | time | The condition did not match |

Validation rejects:

- a handle the source node does not declare;
- more than one edge from the same handle;
- a missing edge for a non-terminal output;
- an outgoing edge from a terminal node;
- an unknown source or target;
- a node that cannot be reached from `entry`.

Cycles are allowed because a menu can intentionally loop back to itself.

## 5. Compilation

The compiler produces deterministic named extensions.

Given a flow named `office` with entry `answer`, the output begins:

```xml
<extension name="fs_flow_office_entry">
  <condition field="destination_number" expression="^1000$">
    <action application="set" data="fs_switch_flow=office"/>
    <action application="transfer" data="fs_flow_office_answer XML default"/>
  </condition>
</extension>
<extension name="fs_flow_office_answer">
  <condition field="destination_number" expression="^fs_flow_office_answer$">
    <action application="answer"/>
    <action application="transfer" data="fs_flow_office_menu XML default"/>
  </condition>
</extension>
```

A menu node runs its actions, then transfers to a branch selector:

```xml
<extension name="fs_flow_office_menu">
  <condition field="destination_number" expression="^fs_flow_office_menu$">
    <action application="set" data="menu_digit="/>
    <action application="play_and_get_digits"
            data="1 1 1 5000 # ivr/main.wav ivr/ivr-that_was_an_invalid_entry.wav menu_digit [12]"/>
    <action application="transfer" data="fs_flow_office_menu__select XML default"/>
  </condition>
</extension>
<extension name="fs_flow_office_menu__select">
  <condition field="destination_number" expression="^fs_flow_office_menu__select$"/>
  <condition field="${menu_digit}" expression="^1$">
    <action application="transfer" data="fs_flow_office_sales XML default"/>
  </condition>
</extension>
<extension name="fs_flow_office_menu__select_digit_2">
  <condition field="destination_number" expression="^fs_flow_office_menu__select$"/>
  <condition field="${menu_digit}" expression="^2$">
    <action application="transfer" data="fs_flow_office_support XML default"/>
  </condition>
</extension>
<extension name="fs_flow_office_menu__select_timeout">
  <condition field="destination_number" expression="^fs_flow_office_menu__select$"/>
  <condition field="${menu_digit}" expression="^$">
    <action application="transfer" data="fs_flow_office_closed XML default"/>
  </condition>
</extension>
```

Every selector re-checks the dispatch destination and adds its own branch
condition. FreeSWITCH evaluates peer conditions with AND semantics and scans
extensions in document order, so a failed selector condition falls through to
the next selector. This avoids relying on nested-condition break behavior and
keeps branches, joins and loops flat and diffable.

The entry extension matches the real destination. Every node extension matches
its own synthetic name.

### Why not inline the whole graph?

Inlining would require duplicating shared downstream actions into every branch.
Named extensions plus transfers allow a DAG or an intentional loop without
combinatorial growth.

### Operational caution

A broad catch-all extension with a lower priority can intercept an
`fs_flow_...` destination before the synthetic extension is reached. Semantic
flow extensions must be emitted before catch-alls. The future publish validator
must check this; until then, keep semantic flows above broad catch-alls in the
priority order.

## 6. Compatibility with raw graphs

`FS Dialplan.graph_format` selects the compiler:

- `raw` uses the original linear compiler in `dialplan.py`;
- `semantic` uses `flow.py`.

`compile_extension(plan)` is the adapter. `compile_dialplan`, XML-curl and the
preview endpoint therefore work with both formats. The console routes semantic
documents to `SemanticFlowEditor.vue` and raw documents to the original canvas,
so neither editor can overwrite the other format.

The semantic editor uses four whitelisted helpers:

- `get_flow_catalog()` — the palette and node metadata;
- `validate_semantic_flow(graph)` — the same strict validation used by save;
- `simulate_route(graph=..., destination=..., at=..., digits=...)` — walks the
  graph with call inputs and returns the node path taken;
- `preview_dialplan(graph=..., graph_format="semantic")` — XML for an unsaved
  flow.

## 7. Route simulator

The route simulator walks the Draft graph, never the compiled XML. It answers
"what happens if a call reaches this Flow at 14:30 and presses 2?" before an
administrator publishes. Inputs are deliberately small:

| Input | Meaning |
|---|---|
| `destination` | Dialed number, used by the Flow pattern and time fields |
| `at` | Simulated clock as an ISO datetime, `HH:MM` or `HHMM`; defaults to now |
| `digits` | Caller keypresses, consumed in order by menus |
| `variables` | Initial channel variables, as a JSON object |

The simulator starts at `entry`, follows the edge for the port each node takes,
and stops at a terminal node. A menu consumes up to `tries` digits, follows
`digit:<d>` for a valid option, and falls back to `timeout` when no valid digit
is available. A time node evaluates `field` against `at` and follows `match` or
`no_match`. Supported fields are `destination_number`,
`${destination_number}`, `${strftime(FORMAT)}` and variables set earlier in the
Flow. An unsupported field returns an error rather than guessing a branch.

The response includes `valid`, `matched`, `path`, `terminal`, `outcome`,
`variables`, `warnings` and `errors`. Each path step names the node, its type,
the port taken and a human-readable detail. If the destination does not match
the Flow's `destination_number` pattern, `matched` is false and the path is
empty. Intentional loops stop at `max_steps` (default 50) and return
`truncated: true`.

The simulator is a projection of the Draft, like the table and XML tabs. It does
not publish, invalidate the call-setup cache or call FreeSWITCH.

## 8. Publish lifecycle

`FS Dialplan.graph` is the editable **Draft**. Saving validates and recompiles
the Draft into `compiled_xml`, but that XML is preview only.

Publishing:

1. compiles the saved Draft with the same Compiler;
2. appends an immutable `FS Dialplan Version` row with the graph, format, XML,
   context, priority and audit fields;
3. updates `published_xml`, `published_graph`, `published_context`,
   `published_priority`, `published_tenant`, `published_version`, `published_on`
   and `published_by`;
4. invalidates the call-setup cache after commit;
5. asks FreeSWITCH to `reloadxml`, best-effort.

The xml-curl call-setup path serves the whole document from the Redis cache in
`call_setup.py`, keyed by tenant and context. It never compiles on the request
path and reads only `published_xml`, `published_context`, `published_priority`
and `published_tenant` when the cache is cold. Draft graph fields are ignored.
Every served document is filtered by tenant. The alpha resolves every domain and
context to the `default` Tenant; domain/context mapping is a later slice. A
failed publish leaves the previous Published version in place; that is the
last-known-good XML. A failed rebuild serves the last-known-good cache entry,
and with none the handler returns FreeSWITCH's not-found document.

`publish_status` is `Published` only while the compiled Draft matches the
Published XML, context, priority and Tenant. Any other saved change makes it
`Draft` again. Enabling or disabling a Flow is operational and takes effect without a
new publish.

Before publishing, `get_dialplan_diff(name)` compares the saved Draft with the
Published snapshot. It reports the entry step, context/priority/format changes,
added, removed and changed nodes, added and removed connections, and a unified
XML diff. Node identity is the node id; connection identity is source, output
Port and target, so moving a node or renumbering an edge id is not a routing
change. The diff is read-only: it does not save, publish or invalidate the
call-setup cache.

Rollback moves the Published pointer to an earlier version row. It does not
overwrite the Draft, so in-progress edits survive. The APIs are
`publish_dialplan`, `rollback_dialplan`, `get_dialplan_versions` and
`get_dialplan_diff`.

Existing valid Flows are published once by the upgrade patch
`fs_switch.patches.v0_1.publish_existing_flows`.

## 9. Adding a node type

1. Add a renderer in `flow.py` that returns `RenderedNode`.
2. Declare a `NodeSpec` with outputs, required fields, defaults, and optional
   validation/dynamic outputs.
3. Add unit tests for its actions or branches and for invalid data.
4. Add it to the frontend palette through `get_flow_catalog`.
5. Add a golden XML test if it introduces a new XML shape.

Do not let the frontend invent XML. The registry and compiler are the contract.

## 10. Known limitations in v1

- The route simulator evaluates `destination_number`, `${strftime(FORMAT)}` and
  variables set earlier in the Flow. Native FreeSWITCH time fields such as
  `wday`, `hour` and `minute-of-day` are not evaluated yet; use a `strftime`
  field or a `set` variable for a simulatable time branch.
- No holiday calendar node; use `time` with FreeSWITCH condition fields.
- No `menu` option labels in the XML; labels are UI metadata.
- No media library or TTS/ASR nodes yet.
- The alpha is single-tenant: tenant fields and tenant-filtered call-setup
  documents exist, but every domain and context resolves to `default`. Tenant
  UI and domain/context mapping are later.
- No explicit catch-all-protection check yet.

These are deliberate next steps, not hidden behavior.
