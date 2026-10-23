---
name: add-semantic-node
description: Add a Semantic node (Office Hours, Ring Group, Queue, IVR Menu) end to end.
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

1. Run `grilling` on the node: its admin-facing name, its config, its **outcome ports**. Name ports for what happened, never for the FreeSWITCH mechanism.
2. Register it: category, icon, config schema, ports, validator.
3. Write one **Golden test** per port path, red.
4. Write the compile function until green. Read `flow-compiler` first.
5. Add validator rules. Each error names the node id and port.
6. Teach the **Route simulator** the node.
7. Add the canvas node and its property drawer.
8. Add any new term to GLOSSARY.md.

Done when every port has a **Golden test** and a **Route simulator** path.
