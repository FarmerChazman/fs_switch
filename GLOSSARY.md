# FS Switch

A Frappe app that compiles visual call flows into FreeSWITCH configuration and operates the live switch.

## Language

**Flow**:
The graph of nodes and edges an admin designs. The single source of truth for one call-handling behaviour.
_Avoid_: dialplan (that is the compiled artifact), workflow, diagram

**Node**:
One step in a **Flow**. Either a **Semantic node** or a **Raw application node**.

**Semantic node**:
A node named for admin intent (Office Hours, Ring Group, Queue, IVR Menu) with a config schema, **Ports** and a compile function. Registered in the node registry.
_Avoid_: block, widget

**Raw application node**:
A node wrapping one FreeSWITCH application (`playback`, `bridge`). Lives in Advanced mode.

**Port**:
A named connection point on a node, named for its outcome: `match`, `no-match`, `digit`, `timeout`, `success`, `failure`. **Edges** attach to ports.
_Avoid_: handle (use only when quoting Vue Flow's `sourceHandle`)

**Edge**:
A connection from one node's output **Port** to another node's input port.

**Compiler**:
The Python code that turns a **Flow** into FreeSWITCH XML.

**Projection**:
A view of a **Flow**: canvas, table or XML preview. A projection never holds data of its own.

**Draft**:
The editable version of a **Flow**. Never served to FreeSWITCH.

**Published**:
A validated, compiled version of a **Flow** that FreeSWITCH may be served. **Rollback** returns to the previous published version.

**Call-setup path**:
Every code path FreeSWITCH waits on while routing a call: the xml-curl handlers for directory, dialplan and callcenter.conf.

**Last-known-good**:
The most recent **Published** XML for a tenant and context, served when compilation or lookup fails.

**Golden test**:
A test with a fixture **Flow** in and the exact expected XML out.

**Route simulator**:
Walks a **Flow** with given call inputs (destination, time) and returns the node path taken. Walks the graph, never the XML.

**Tenant**:
One customer organisation. Owns domains, contexts, DIDs, extensions and flows.
_Avoid_: company, org, account

**Domain** / **Context**:
FreeSWITCH routing labels resolved to a **Tenant**. Routing labels, not a security boundary.

**DID**:
An inbound number assigned to a **Tenant**. Appears as a starting node on the canvas.

**Control plane** / **Data plane**:
Frappe holds configuration, permissions, audit and realtime fan-out. FreeSWITCH holds SIP, media, queues and routing.

**Listener**:
The single long-lived ESL connection that normalises FreeSWITCH events into `fs_switch_call` and `fs_switch_agent`.

## Flagged ambiguities

- The existing DocType is named "FS Dialplan" but stores a **Flow** plus its compiled XML. Resolved: say **Flow** for the graph and **dialplan** only for the XML it compiles to.
