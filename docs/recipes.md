---
title: "Flow recipes"
space: "FS Switch"
---

These are small, buildable examples. They use the semantic nodes in
[`flows.md`](flows.md) and the DID rules in [`dids.md`](dids.md). Use your own
numbers, extensions and queue names.

## Recipe 1: office-hours menu with queue fallback

**Goal:** a main number reaches a two-option menu during office hours, sends
callers to a queue or ring group, and sends after-hours callers to voicemail.

**Flow**

```text
                 ┌───────────┐
                 │  Answer   │
                 └─────┬─────┘
                       │
                 ┌─────▼────────┐
                 │ Time condition│
                 │ 09:00–17:59  │
                 └──┬────────┬──┘
                 match     no-match
                   │          │
             ┌─────▼─────┐  ┌─▼──────────────┐
             │ IVR menu  │  │ Play closed     │
             │ 1 Sales   │  │ Voicemail       │
             │ 2 Support │  └─────────────────┘
             └─┬───────┬─┘
        digit 1│       │digit 2
          ┌────▼──┐ ┌──▼──────────┐
          │ Ring  │ │ Queue       │
          │ group │ │ support     │
          └───┬───┘ └──────┬──────┘
              │            │
          ┌───▼───┐    ┌───▼────┐
          │Hang up│    │Hang up │
          └───────┘    └────────┘
```

**Settings**

| Item | Value |
|---|---|
| Destination | `^\+?14155550101$` |
| Context | Tenant default context |
| Time field | `${strftime(%H%M)}` |
| Time expression | `^(09|1[0-7])[0-9]{2}$` |
| Menu prompt | Your greeting |
| Options | `1` Sales, `2` Support |
| Digit 1 | Ring group with extension `7101` |
| Digit 2 | Queue `accept_support` |
| Timeout | Voicemail mailbox `7101` |
| No-match | Play closed, then voicemail |

The time expression is a FreeSWITCH regex over a 24-hour `HHMM` value. It covers
09:00 through 17:59. Adjust it for your schedule. There is no holiday calendar
node yet; add an outer time condition or a separate holiday Flow until one
exists.

## Recipe 2: after-hours voicemail

**Goal:** route all calls outside office hours to a closed message and voicemail
without changing the daytime Flow.

```text
Answer → Time condition ─ match → existing daytime menu
                         └ no-match → Play closed → Voicemail
```

Use one Flow with the time condition first. Two Published Flows with the same
destination do not alternate by time: FreeSWITCH chooses one by priority, so a
lower-priority after-hours Flow would never run while the daytime Flow is
enabled. If you need separate Flows, give them different destinations or drive
the switch from an external schedule and enable one at a time.

Test both branches with **Simulate**. Verify the time expression against the
FreeSWITCH server's local time, not the browser's time.

## Recipe 3: queue with a backup tier

**Goal:** a support queue uses primary agents first and a backup queue when the
primary queue is busy or no agent is available.

1. Create the primary queue `support` with agents at level 1.
2. Create `support_backup` with its backup agents.
3. On `support`, set **Backup queue** to `support_backup`.
4. Set **Maximum wait (seconds)** to the caller's maximum hold time.
5. Put the queue node in the Flow, followed by voicemail or hangup.

```text
Answer → Queue support → Voicemail
```

The backup queue's agents are added at level 2 when the backup queue is in the
same Tenant. The queue strategy still decides which available agent is offered
the call. The `Next` port runs after the queue application returns, so use it for
the after-queue destination.

Test with:

- one primary agent Available;
- both primary agents On Break;
- all agents Logged Out;
- max wait reached with no answer.

## Recipe 4: DID and Flow pattern cookbook

| Carrier sends | DID stored | Flow destination |
|---|---|---|
| `+14155550101` | `+14155550101` | `^\+14155550101$` |
| `14155550101` | `14155550101` | `^14155550101$` |
| either | `+14155550101` | `^\+?14155550101$` |
| `+1415555010x` block | one DID per number | `^\+?1415555010[0-9]$` |

The DID **Assigned Flow** is documentation. The regex does the matching. If the
carrier adds a country code or a `+`, the pattern must accept it.

The public DID map routes enabled DIDs to their Published Flow or the Tenant
main number. See [DIDs and inbound numbers](dids.md) for the exact fallback and
cache behavior.

## Recipe 5: ring a group, then voicemail

```text
Answer → Ring group (7101, 7102, timeout 30s) → Voicemail 7101
```

The ring group endpoint list accepts extension numbers or explicit dial strings.
The timeout is passed to FreeSWITCH as `leg_timeout`. The `Next` port runs after
the bridge ends, so place the voicemail or hangup there. This is not the same as
a queue: a ring group does not hold callers in a call-center tier.

Test:

- one endpoint registered;
- both endpoints registered;
- no endpoints registered;
- voicemail path/mailbox exists in FreeSWITCH.

## Build order

1. Create the extension and queue in the active Tenant.
2. Create the Flow and set the destination/context.
3. Add and connect nodes; validate.
4. Simulate the normal, timeout and after-hours paths.
5. Save, review **Draft vs Published**, publish.
6. Add the DID and align the pattern.
7. Test from a real softphone.
8. Check **Live → Channels** and the wallboard.

## Related pages

- [Flows and the semantic editor](flows.md)
- [DIDs and inbound numbers](dids.md)
- [Queues and agents](queues.md)
- [Extensions and endpoints](extensions.md)
- [Limitations](limitations.md)
