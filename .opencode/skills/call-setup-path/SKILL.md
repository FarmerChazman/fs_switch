---
name: call-setup-path
description: Rules for xml-curl handlers (directory, dialplan, callcenter.conf). Use when touching a handler, its cache, or anything FreeSWITCH waits on while routing a call.
---

FreeSWITCH waits on this path. A slow or failing handler drops calls.

- Compile at publish time. A handler reads **Published** XML from cache and does indexed lookups only.
- Resolve the **Tenant** from domain and context first, and scope every query to it.
- Check the xml-curl secret before any lookup.
- On any failure, serve **Last-known-good**. With none, return the not-found document: `<document type="freeswitch/xml"><section name="result"><result status="not found"/></section></document>`.
- Invalidate the cache from the publish step, nowhere else.
- Handlers never write.

Test a handler by replaying a captured POST body, with the cache warm, cold and Frappe-down.
