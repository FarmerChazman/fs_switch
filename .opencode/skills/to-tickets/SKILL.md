---
name: to-tickets
description: Break a spec or plan into tracer-bullet tickets at docs/tickets, each declaring what blocks it.
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

1. Gather context: the spec I point at, or this conversation.
2. Explore the repo.
3. Draft **tracer bullet** tickets: each a thin vertical slice through every layer it needs (DocType, **Compiler**, xml-curl, console), demoable on its own. Slice by behaviour, never by layer.
4. Show me the draft with its blocking edges. Revise until I approve.
5. Write `docs/tickets/<spec-slug>/NN-title.md`.

## Ticket

```
# <title>
## Build
End-to-end behaviour, in GLOSSARY.md terms.
## Done when
Checkable criteria. Each names a test or an observable result.
## Blocked by
Ticket numbers, or none.
## Kind
AFK (an agent can finish alone) or HITL (needs me).
```

Done when the first ticket is unblocked and demoable.
