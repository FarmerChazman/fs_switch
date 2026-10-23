---
name: grill-with-docs
description: Grilling session that also sharpens GLOSSARY.md and records ADRs. Start here for any change.
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

Run `grilling`, and grow the shared language as you go.

## Language

When I use a term that clashes with GLOSSARY.md or means two things, stop and resolve it. Write the resolution into GLOSSARY.md the moment it lands: the term, one definition, an _Avoid_ line for the rejected synonyms.

## Stress

Test each decision against these cases, and put the ones that break it to me:

- two DIDs reaching one **Flow**
- a **Tenant** boundary crossing
- Frappe unreachable mid-call
- a **Flow** with a branch nobody tested

## Decisions

Write an ADR to `docs/adr/NNNN-title.md` when a decision is hard to reverse, surprising without context, and the result of a real trade-off. One paragraph each: context, decision, why.

Done when every term in play is in GLOSSARY.md and every qualifying decision has an ADR.
