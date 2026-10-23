---
name: flow-compiler
description: Rules for the Flow graph, node registry, Compiler, validation and publish pipeline. Use when touching Flow, nodes, ports, validation, publish or rollback.
---

## Pipeline

**Draft** → validate → compile → diff → **Published** → `reloadxml`. **Rollback** returns to the previous **Published**. FreeSWITCH never sees a **Draft**.

## Graph

- **Edges** attach to **Ports** (Vue Flow `sourceHandle` and `targetHandle`). Name ports for outcomes: `match`, `no-match`, `digit`, `timeout`, `success`, `failure`.
- Every **Semantic node** lives in the node registry with: category, icon, config schema, ports, validator, compile function.
- **Raw application nodes** live in Advanced mode and pass through the same validation.

## Compile

- A node compiles to an XML fragment. Branching compiles to nested conditions or priority-ordered extensions. Pick one per node kind and record it in an ADR.
- Compile in Python only. The table and XML preview read the compiler's output.

## Validate

Report each of these with the node id and port, so the canvas can highlight it:

- unreachable node
- dangling edge
- cycle
- missing port
- missing required config

## Publish

Publish is atomic: compile, store, invalidate the cache, then reload. A failed compile leaves **Last-known-good** serving.
