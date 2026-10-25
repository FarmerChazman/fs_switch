---
title: "DIDs and inbound numbers"
space: "FS Switch"
---

A **DID** (Direct Inward Dialling number) is an inbound phone number assigned to
a Tenant. The **DIDs** page records the number, which Tenant owns it, whether it
is enabled, and which Flow should handle it.

DIDs are the routing map for calls entering FreeSWITCH's shared `public`
context. An enabled DID assigned to an enabled, Published Flow compiles a
public-context transfer into that Flow's Tenant context. A DID without a Flow
falls back to its Tenant's **Main inbound number**. The Flow's **Destination**
pattern must still match the number FreeSWITCH receives.

![DIDs list](screenshots/dids.png)

*The active Tenant's inbound numbers and intended Flows*

## Add an inbound number

1. Select the Tenant in the top bar.
2. Open **Telephony → DIDs**.
3. Click **New DID**.
4. Enter the number in the form the carrier sends it, including `+` when the
   carrier includes it. Spaces, hyphens, parentheses and a `tel:` prefix are
   removed on save.
5. Keep **Enabled** on.
6. Optionally select the **Assigned Flow**. The Flow must belong to the same
   Tenant.
7. Add a description that identifies the carrier, country or purpose.
8. Click **Save**.

![New DID form](screenshots/new-did.png)

*Adding an inbound number*

### Number normalization

FS Switch stores the number with spaces, punctuation and an optional `tel:`
prefix removed, but keeps a leading `+`:

| Entered | Stored |
|---|---|
| `tel:+1 (415) 555-0101` | `+14155550101` |
| `+1 415 555 0101` | `+14155550101` |
| `1-415-555-0101` | `14155550101` |

Uniqueness is checked on the digits only. `+14155550101` and `14155550101`
cannot both exist in the inventory, and a number can belong to only one Tenant.

## Align the Flow destination pattern

The **Destination** field on a Flow is a FreeSWITCH regular expression. It must
match the destination number as FreeSWITCH receives it from the carrier, not
necessarily the way the DID is displayed in the inventory.

Use the narrowest pattern that covers the carrier's format:

| Carrier sends | Flow destination pattern |
|---|---|
| `+14155550101` | `^\+14155550101$` |
| `14155550101` | `^14155550101$` |
| Either form | `^\+?14155550101$` |
| A block of numbers | `^\+?1415555010[0-9]$` |

`+` is a regular-expression operator, so it must be escaped as `\+`. The optional
form `\+?` accepts one or zero plus signs. Do not add a leading or trailing space.
Use the Flow **Simulate** tab with the exact destination the carrier sends and
confirm that the expected branch is reached.

### Assigned Flow and Tenant fallback

The public route is chosen in this order:

1. **Enabled DID with an enabled, Published Flow** → transfer to the Flow's
   published Tenant context.
2. **Enabled DID with no Flow, and the Tenant has a Main inbound number** →
   transfer to the Tenant main number in the Tenant context.
3. **No eligible Flow and no Tenant main number** → no public route; the call
   receives FreeSWITCH's not-found result rather than being sent to the wrong
   Tenant.

An assigned Flow that is disabled, unpublished, belongs to another Tenant, or
targets `public` is skipped. It does not silently fall back to the Tenant main
number. This makes a broken assignment visible instead of hiding it.

The Flow destination pattern still has to match the carrier's format. If the
DID says `+14155550101` and the Flow pattern is `^14155550101$`, a carrier that
sends the plus will not match.

## Inbound call path

The public dialplan is compiled from the enabled DID inventory across all
enabled Tenants:

```text
Carrier → gateway → public context → DID route
        → Tenant context → Flow destination pattern
```

The route map is served from the same cached dialplan document as the rest of
the Tenant configuration. It is rebuilt when a DID, Flow or Tenant changes.

- A carrier call entering `public` can reach the correct Tenant without a
  per-DID FreeSWITCH file.
- A Flow that is not Published is not routed.
- A DID that is disabled or belongs to a disabled Tenant is not routed.
- The global **Settings → Main inbound number** is kept as the final legacy
  fallback when no DID route claims the number.

## Main inbound numbers

There are two related settings:

| Setting | Scope | Purpose |
|---|---|---|
| **Tenant → Main inbound number** | One Tenant | Fallback target for that Tenant's DIDs without an assigned Flow. |
| **Settings → Main inbound number** | Global | Legacy public-context fallback when no DID route matches. Also used for the default Tenant on a simple install. |

The Tenant main number is stored on the Tenant and is used with the Tenant's
default context. The global setting remains available for compatibility and for
a simple single-Tenant deployment; do not confuse the two.

Keep these values aligned:

1. The carrier's actual number.
2. The Tenant main number or global main DID.
3. The DID record in the Tenant inventory.
4. The Flow's destination pattern.
5. The number allowed by the gateway or carrier.

Changing the DID inventory does not change either main number. Changing a main
number does not change any Flow pattern.

## Cache and publication

The public route map is part of the dialplan cache. These changes invalidate it:

- saving or deleting a DID;
- publishing, rolling back or enabling/disabling a Flow;
- changing a Tenant or the global Settings.

A normal Draft save does not change public routing. Publish the Flow and verify
the Published version before testing the number.

## Disable or delete a DID

Disabling or deleting a DID removes its public route on the next cache rebuild.
It does not stop a carrier from delivering the number; remove or change the
carrier route separately. Deleting a DID does not delete its assigned Flow.

If the DID was the only route for a number, the global main-DID fallback may
still match. Check the actual call path after changing the inventory.

## Checklist for a new inbound number

- [ ] The number is in the correct Tenant's DID inventory.
- [ ] The carrier format is known, including the leading `+`.
- [ ] The Flow destination pattern matches that exact format.
- [ ] The Flow is published, not just saved.
- [ ] The Flow context is the Tenant's default context.
- [ ] The DID is enabled and assigned to the Published Flow, or the Tenant has a
      Main inbound number.
- [ ] The gateway/carrier is sending calls to `public` or directly to the
      Tenant context.
- [ ] The public route map returns the expected transfer.
- [ ] A test call reaches the expected Flow step.
- [ ] The call appears in **Live → Channels** and, if queued, in the wallboard.

## Troubleshooting

| Symptom | Check |
|---|---|
| `DID ... is already in the inventory` | Numbers are unique across Tenants on digits alone. Remove the duplicate or use a different number. |
| `Flow ... belongs to another Tenant` | The Assigned Flow must belong to the DID's Tenant. |
| Flow simulator matches, but the real call does not | The carrier may add or remove `+`, a country code or a prefix. Compare the actual FreeSWITCH destination with the pattern. |
| The call reaches the wrong Flow | Check Flow priority, the destination pattern, and whether the old Published version is still being served. |
| Another Tenant's DID works but this one does not | Check that the DID is enabled, the Flow is Published and belongs to the same Tenant, and the Tenant is enabled. |
| The DID is disabled but calls still arrive | Removing the DID route does not stop the carrier. Change the carrier route and check the global main-DID fallback. |
| The DID has no assigned Flow | Set the Tenant **Main inbound number** or assign a Published Flow; an unassigned DID has no route without a Tenant fallback. |
| Public XML has the old route | The DID/Flow change should invalidate the dialplan cache; wait for the rebuild or check the invalidation/error log. |

## Related pages

- [Tenants and membership](tenants.md)
- [Gateways and carrier trunks](gateways.md)
- [Flows](flows.md)
- [Settings](settings.md)
