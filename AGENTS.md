# FS Switch

FS Switch is a Frappe app that makes FreeSWITCH 1.10 operable by non-telecom admins. Frappe is the control plane. FreeSWITCH is the data plane.

Stack: Frappe (Python) for DocTypes, permissions, audit and compilation. Vue 3, PrimeVue and Vue Flow for the console. mod_xml_curl serves configuration. ESL carries live commands and events. Read the repo's package and bench config for commands.

Use the terms in GLOSSARY.md in code, tests, commits and replies.

## Invariants

- The flow graph is the single source of truth. Canvas, table and XML preview are projections of it. XML is compiler output and stays read-only everywhere.
- Python compiles and validates. The browser sends a graph and receives errors and a preview.
- Frappe enforces tenant scope. FreeSWITCH domains and contexts are routing labels.
- Frappe is the only backend. Add no second service.
- FreeSWITCH waits on the call-setup path. Serve published XML from cache.

## Product

Read `docs/product-thesis.txt` when a scope question comes up. The two `docs/research-*.txt` files are raw source material.

## Skills

Run `/ask-fs-switch` to pick a flow.

## Plans

- Make plans extremely concise. Sacrifice grammar for concision.
- End each plan with a list of unresolved questions, if any.
