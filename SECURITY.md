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
- changing Published XML or version history without publish or rollback,
- exposing SIP or ESL credentials,
- escaping the console's System Manager check,
- serving Draft XML to FreeSWITCH.

## Deployment checklist

- Use HTTPS for the Frappe site and `wss://` for browser softphones.
- Set a long, random `FS_SWITCH_XML_CURL_SECRET`; the XML-curl endpoint is
  reachable by guests but rejects requests without it.
- Set a strong ESL password and keep port 8021 inside the private network.
- Limit console access to System Managers until role-based access is added.
- Keep the default Tenant and all tenant fields under change control. Tenant
  fields are fixed after creation; tenant-scoped create permissions are not
  enforced yet.
- Do not commit `.env`, SIP credentials or carrier hostnames.
- Review the FreeSWITCH ACLs before exposing SIP to the public internet.
- Back up MariaDB and the Redis cache configuration. Last-known-good XML is a
  runtime fallback, not a backup.
