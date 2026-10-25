---
title: "Extensions and endpoints"
space: "FS Switch"
---

An **FS Extension** is a SIP endpoint owned by one Tenant. It links a FreeSWITCH
extension number to a Frappe user, a SIP password and the Tenant's routing
context. The directory document served to FreeSWITCH is built from these
records.

![Extensions list](screenshots/extensions.png)

*The Tenant's SIP endpoints*

## Create an extension

1. Select the Tenant in the top bar.
2. Open **Telephony → Extensions**.
3. Click **New Extension**.
4. Choose the Tenant. It defaults to the active Tenant and is fixed after save.
5. Enter the extension number, for example `1001`.
6. Enter a display name and the Frappe user who owns the endpoint.
7. Set a strong **SIP password**.
8. Leave **Context** blank to use the Tenant's default context. If you enter a
   context, it must be the Tenant's context.
9. Optionally set caller ID fields and voicemail.
10. Set **Agent status** to `Logged Out`, `Available` or `On Break`.
11. Keep **Enabled** on and save.

![New Extension form](screenshots/new-extension.png)

*Creating a SIP endpoint*

The extension owner can open **My extension**, reveal the SIP password and use
the WebSocket URL with a SIP or WebRTC softphone.

## Extension fields

| Field | Purpose |
|---|---|
| **Extension** | SIP user/number. Unique inside the Tenant. |
| **Tenant** | Owner Tenant; fixed after creation. |
| **Display name** | Name shown in the console and used for the effective caller ID name. |
| **Frappe user** | User who can see the endpoint in **My extension**. |
| **SIP password** | Password used by the directory and the softphone. Required. |
| **Context** | Optional endpoint context. Leave blank for the Tenant context; a non-matching context is rejected. |
| **Caller ID name / number** | Endpoint caller-ID metadata. The directory uses the display name or User full name for the effective name, and the number falls back through extension, outbound caller ID, Tenant and extension number. |
| **Outbound caller ID** | Extension-level fallback for the effective caller-ID number. |
| **Voicemail enabled** | Records that the endpoint has voicemail. A Flow still needs a **Voicemail** step to send a call there. |
| **Agent status** | Whether the endpoint is available to call-center queues. |
| **Enabled** | Whether FreeSWITCH should load the endpoint. |
| **Notes** | Internal notes. |

The natural extension number is unique inside one Tenant. The document name is
Tenant-qualified, for example `accept-a::7101`.

## SIP registration and WebRTC

**My extension** shows the endpoint owner:

- the extension and SIP domain;
- the WebSocket URL, normally `ws://localhost:5066` in a local lab;
- the SIP password behind **Reveal**;
- the current agent status.

Use a SIP or WebRTC softphone and register with the extension, SIP password and
WebSocket URL. The console does not include an embedded softphone in this alpha.
For a local stack use `ws://`; `wss://` requires a trusted TLS certificate.

The local FreeSWITCH `webrtc` profile accepts RFC1918 ICE candidates. A public
deployment needs a WAN/TURN candidate plan and a trusted certificate.

## Agent status and queues

The agent status is written into `callcenter.conf` for extensions that are
members of a queue:

- **Available** - eligible to receive queue calls.
- **On Break** - visible but not available.
- **Logged Out** - not available for queue calls.

An extension must also be enabled and listed as an agent or backup tier on the
queue. Changing status from **My extension** sends an ESL `callcenter_config`
command; a queue member that is not loaded in FreeSWITCH cannot receive calls.

## Internal calls

When **Settings → Allow internal calls** is enabled, the compiled Tenant
dialplan accepts 3–6 digit destinations and bridges them to
`user/$1@${domain_name}`. This lets registered extensions dial each other.

Turn it off when extension-to-extension dialling should not be allowed. The
setting applies to the compiled dialplan; publish or reload so FreeSWITCH fetches
the current document.

## Caller ID and voicemail

The effective caller-ID number is chosen from:

1. the extension's caller ID number;
2. the extension's outbound caller ID;
3. the Tenant's outbound caller ID;
4. the extension number.

The directory builds the effective caller-ID name from the display name or, if
blank, the linked User's full name. Use the display name as the operator-facing
name.

Voicemail paths are configured in **Settings**. An extension's voicemail flag is
metadata; a Flow must reach a **Voicemail** node with a mailbox to actually send
the call to voicemail.

## Disable, delete and rename

- Disabling an extension removes it from the directory and agent list on the
  next configuration fetch.
- Deleting an extension removes the endpoint and its queue memberships should be
  cleaned up separately.
- The document name is generated from the extension number at creation.
  Changing the extension field later does not rename the stored document; create
  a new extension and migrate the user/softphone if the number must change.
- Changing the Tenant is not allowed. Tenant ownership is fixed after creation.

Directory and `callcenter.conf` caches are invalidated after an extension save or
delete. FreeSWITCH fetches the new document on its next configuration request;
run `reloadxml` if it does not pick the change up immediately.

## Troubleshooting

| Symptom | Check |
|---|---|
| Softphone cannot register | SIP password, domain, WebSocket URL, extension enabled, and FreeSWITCH profile. |
| `My extension` is empty | The signed-in user is not linked to an extension in the active Tenant. |
| Agent does not receive queue calls | Extension enabled, agent status `Available`, queue membership and tier loaded in FreeSWITCH. |
| Extension context rejected | A non-blank context must equal the Tenant's default context. |
| Caller ID is wrong | Check extension number, outbound caller ID, Tenant caller ID, and the gateway/carrier override. |
| Extension-to-extension calls fail | Check **Allow internal calls**, registration of both endpoints, and the 3–6 digit destination rule. |
| Old password still works | FreeSWITCH has not fetched a new directory document. Reload XML/directory and re-register. |

## Related pages

- [Tenants and membership](tenants.md)
- [Queues](queues.md)
- [Flows](flows.md)
- [Live operations](live-operations.md)
- [Settings](settings.md)
