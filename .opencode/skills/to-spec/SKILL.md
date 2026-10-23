---
name: to-spec
description: Turn the current conversation into a spec at docs/specs. No interview, synthesis only.
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

The grilling already happened. Synthesize what the conversation settled.

1. Explore the repo to ground the spec in the current code.
2. Name the **test seams**: the boundaries where behaviour is observable. Candidates: **Compiler**, validator, **Route simulator**, xml-curl handler, **Listener** normaliser. Confirm them with me before writing.
3. Write `docs/specs/<slug>.md` from the template below.

## Template

```
# <title>

## Problem
## Solution
## User stories
As a <admin | supervisor | engineer>, I want <behaviour>, so that <outcome>.
## Modules
Each touched module and its interface. Prefer a deep module: much behaviour behind a small interface.
## Test seams
## Out of scope
```

Done when the spec uses GLOSSARY.md terms only and I have confirmed the seams.
