---
name: implement
description: Build one ticket or a spec's slice, driving tdd at the agreed seams and closing with proof.
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

1. Read the ticket and the spec it came from.
2. Drive `tdd` at the seams the spec names.
3. Produce proof for every "Done when" line, from this list:
   - **Golden test** green
   - **Route simulator** path for the scenario
   - for **Call-setup path** changes, the handler's response to a captured POST body
   - for live behaviour, an `fs_cli` or ESL observation
4. Review your own diff against GLOSSARY.md and the AGENTS.md invariants. Fix what breaks them.
5. Commit one ticket per commit.

Done when each criterion has its proof attached to the commit message or ticket.
