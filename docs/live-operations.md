---
title: "Live operations and wallboard"
space: "FS Switch"
---

The **Live** workspace is the operational view of FreeSWITCH. It uses the ESL
listener for events and reads a live snapshot for the current state. The console
applies events over Socket.IO and falls back to polling when the socket is
disconnected.

A **Supervisor** or **Tenant Admin** can open Live. Agents cannot see the Live
tree.

## Live Channels

![Live channels](screenshots/live-channels.png)

*Active call legs read from ESL*

Channels shows the active legs with caller, destination, Tenant context, state
and creation time. A Supervisor or Tenant Admin can:

- **Hang up** a channel.
- **Transfer** a channel to another destination.

Live actions are checked against the active Tenant and the target channel before
they reach ESL. A supervisor in one Tenant cannot act on another Tenant's rows.

The destination can be an internal compiled Flow extension while the call is
executing. Use the queue/agent path in the wallboard for the operator-facing
call path.

## Registrations

**Live → Registrations** lists the SIP registrations currently known to
FreeSWITCH: user, realm, contact, network address and expiry. A missing
registration explains why a softphone or queue agent cannot receive calls.

Registration events are published by the listener as `fs_switch_registration`
events. The console applies them in place; a disconnected console polls a
snapshot.

## Agents

![Live agents](screenshots/live-agents.png)

*Agent status and queue state*

The Agents grid shows each call-center agent and its current state. A Supervisor
or Tenant Admin can set **Available**, **On Break** or **Logged Out** from the
row. The change is persisted on the extension and sent to ESL
`callcenter_config`.

An extension only appears as a queue agent when it is enabled and selected on a
queue or backup queue. Queue calls require **Available** and a registered
endpoint.

## Wallboard

![Wallboard](screenshots/wallboard.png)

*Queue depth, agent availability and an active queued call*

The wallboard projects the live snapshot into:

| Metric | Meaning |
|---|---|
| **Waiting calls** | Callers waiting in queues. |
| **Longest wait** | Longest current queue wait in the snapshot. |
| **Available agents** | Available and waiting agents. |
| **Busy agents** | Agents receiving or in a queue call. |
| **On break / logged out** | Agent status counts. |
| **Active calls** | Deduplicated active call legs. |
| **Answer rate** | Answered / (answered + abandoned) from queue counters. |
| **Queue rows** | Per-queue waiting, configured max wait, answered and abandoned. |
| **Active call paths** | Caller → queue or destination → agent when available. |

A call path is de-duplicated by `call_uuid`, so the caller and agent legs do not
appear as two unrelated calls. Queue depth comes from active `callcenter`
channels, not a separate counter.

The wallboard refreshes every 10 seconds while open and also applies live
Socket.IO events.

## Listen, Whisper and Barge

On an active call path, a Supervisor or Tenant Admin can choose:

- **Listen** - hear both parties without speaking.
- **Whisper** - speak to the agent only.
- **Barge** - join the conversation.

The action rings the signed-in supervisor's own extension and starts a
FreeSWITCH `eavesdrop` leg. The supervisor needs:

- an enabled **FS Extension** assigned to their user in the active Tenant;
- a registered SIP/WebRTC softphone;
- the Tenant Supervisor or Admin role.

Whisper uses the agent leg. Barge mixes both legs. The console does not play
monitor audio in the browser yet; the audio is on the supervisor's softphone.

## Realtime and polling

The top bar shows one of:

- **Live push** - Socket.IO connected; events are applied as they arrive.
- **Connecting** - the socket is starting or reconnecting.
- **Polling fallback** - the socket is unavailable; the console polls the live
  snapshot every 30 seconds.

The listener normalizes FreeSWITCH events into `fs_switch_call`,
`fs_switch_agent` and `fs_switch_registration` and publishes them only to the
owning Tenant's Admins/Supervisors and System Managers. The initial snapshot is
taken on load.

If FreeSWITCH is not connected:

- check **Settings → ESL host/port/password**;
- check the FreeSWITCH event-socket configuration and ACL;
- check `docker compose logs freeswitch` and the ESL listener log.

## Permissions

| Role | Channels | Registrations | Agents | Wallboard | Hang up / transfer | Agent status | Listen / Whisper / Barge |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Admin** | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| **Supervisor** | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| **Agent** | No | No | No | No | No | Own status | No |
| **System Manager** | All Tenants | All Tenants | All Tenants | All Tenants | All Tenants | All Tenants | All Tenants |

The live API checks the active Tenant before executing an action. The selector
does not grant access to a Tenant where the user lacks the role.

## Troubleshooting

| Symptom | Check |
|---|---|
| Channels is empty during a call | FreeSWITCH/ESL connection, the call's context, and the active Tenant. |
| Queue depth stays zero | Queue has active callers, queue is loaded, and the call is in the queue's context. |
| Agent says Available but never rings | Extension registration, queue tier, agent state, and FreeSWITCH `callcenter_config`. |
| Wallboard shows duplicate calls | Call-path de-duplication is by `call_uuid`; inspect the raw channel rows if the data itself is duplicated. |
| Listen does nothing | The supervisor has an extension and a registered softphone; check the originate job and ESL reply. |
| Actions fail with permission error | The user needs Supervisor/Admin membership for the active Tenant. |
| Live stops updating | Check **Live push** vs **Polling fallback**; check Socket.IO port 9000 and the Frappe realtime service. |

## Related pages

- [Queues and agents](queues.md)
- [Flows](flows.md)
- [Tenants and membership](tenants.md)
- [Settings](settings.md)
- [`operations.md`](operations.md) - ESL listener, cache and runtime operations
