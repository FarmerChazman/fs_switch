# Security policy

## Supported versions

FS Switch is alpha software. Security fixes target the `main` branch and the
latest tagged release. Older commits are not supported.

## Reporting a vulnerability

Please do not open a public issue for a security problem. Report it privately
through GitHub Security Advisories:

<https://github.com/FarmerChazman/fs_switch/security/advisories/new>

Include:

- the affected version or commit,
- a description and reproduction steps,
- the impact you believe it has,
- any suggested fix.

You will get an acknowledgement as soon as possible. Please give us time to
release a fix before disclosing the issue.

## Scope

Reports are especially useful for:

- bypassing the XML-curl shared secret,
- reading or changing another Tenant's documents,
- acting on another Tenant's live channel or agent,
- changing Published XML or version history without publish or rollback,
- exposing SIP or ESL credentials,
- escaping Tenant membership or the System Manager check,
- serving Draft XML to FreeSWITCH.

## Deployment checklist

- Use HTTPS for the Frappe site and `wss://` for browser softphones.
- Set a long, random `FS_SWITCH_XML_CURL_SECRET`; the XML-curl endpoint is
  reachable by guests but rejects requests without it.
- Set a strong ESL password and keep port 8021 inside the private network. The
  Docker entrypoint uses the `lan` ACL so the Frappe container can connect; do
  not publish 8021 to the host or public internet.
- Use Tenant membership for console access. DocType role permissions grant the
  capability; membership rows and the permission hooks narrow it to the right
  Tenants. System Manager is the global override.
- Keep the default Tenant and all tenant fields under change control. Tenant
  fields are fixed after creation.
- Serve the console and Socket.IO over HTTPS. If the socket uses a separate host
  or port, restrict CORS to the site origin and keep the session cookie on a
  trusted domain.
- Do not commit `.env`, SIP credentials or carrier hostnames.
- Review the FreeSWITCH ACLs before exposing SIP to the public internet.
- Back up MariaDB and the Redis cache configuration. Last-known-good XML is a
  runtime fallback, not a backup.
