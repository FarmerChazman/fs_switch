---
name: ask-fs-switch
description: Pick which FS Switch skill fits the situation. Router over the user-invoked skills.
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

Ask what I am trying to do, then name the skill and say why.

- Unclear idea or change: `/grill-with-docs`
- Conversation already aligned: `/to-spec`
- Spec ready to split: `/to-tickets`
- Ticket ready to build: `/implement`
- New admin-facing node: `/add-semantic-node`

`tdd`, `flow-compiler`, `call-setup-path` and `diagnosing-bugs` are model-invoked and load themselves.
