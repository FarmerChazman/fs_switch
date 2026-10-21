# Security policy

## Reporting a vulnerability

Please do not open a public issue for a security problem. Report it privately to
the maintainers (add the security contact for the public repository here) with:

- the affected version or commit,
- a description and reproduction steps,
- the impact you believe it has,
- any suggested fix.

You will get an acknowledgement as soon as possible. Please give us time to
release a fix before disclosing the issue.

## Deployment checklist

- Use HTTPS for the Frappe site and `wss://` for browser softphones.
- Set a long, random `FS_SWITCH_XML_CURL_SECRET`; the XML-curl endpoint is
  reachable by guests but rejects requests without it.
- Set a strong ESL password and keep port 8021 inside the private network.
- Limit console access to System Managers until role-based access is added.
- Do not commit `.env`, SIP credentials or carrier hostnames.
- Review the FreeSWITCH ACLs before exposing SIP to the public internet.
