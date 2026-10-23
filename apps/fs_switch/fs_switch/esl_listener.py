"""Publish FreeSWITCH call, agent and registration events on Frappe realtime.

Run next to the bench:

    bench --site <site> execute fs_switch.esl_listener.run

Events:
    fs_switch_call          a channel was created, answered, changed or hung up
    fs_switch_agent         a call-center agent changed status or state
    fs_switch_registration  a SIP registration was created or removed

The console subscribes to these events and keeps a slow snapshot poll as a
fallback. Event payloads carry the resolved Tenant so a multi-tenant console can
filter without a second lookup in the browser.
"""

from __future__ import annotations

import time

from fs_switch.esl import ESLConnection, ESLError

EVENTS = (
	"CHANNEL_CREATE CHANNEL_ANSWER CHANNEL_HANGUP_COMPLETE CHANNEL_STATE "
	"CUSTOM callcenter::info REGISTER UNREGISTER"
)
CALL_EVENTS = (
	"CHANNEL_CREATE",
	"CHANNEL_ANSWER",
	"CHANNEL_HANGUP_COMPLETE",
	"CHANNEL_STATE",
)
AGENT_ACTIONS = ("agent-status-change", "agent-state-change", "agent-offering")


def _live_users(tenant: str) -> list[str]:
	"""Return the users allowed to see live rows for a Tenant.

	Realtime is not a permission system. Publishing to every connected browser
	would leak one Tenant's calls to Agents and to other Tenants, so the
	listener resolves the Tenant's Admins and Supervisors plus the global System
	Managers and publishes to those users only.
	"""
	import frappe

	users = set(
		frappe.get_all(
			"FS Tenant Member",
			filters={
				"parent": tenant,
				"enabled": 1,
				"role": ["in", ["Admin", "Supervisor"]],
			},
			pluck="user",
		)
	)
	users.update(
		frappe.get_all(
			"Has Role",
			filters={"parenttype": "User", "role": "System Manager"},
			pluck="parent",
		)
	)
	users.add("Administrator")
	return sorted(user for user in users if user)


def _publish(event: str, payload: dict, user: str | None = None):
	import frappe

	tenant = payload.get("tenant") or "default"
	try:
		recipients = [user] if user else _live_users(tenant)
	except Exception as exc:
		frappe.log_error(title="FS Switch ESL listener recipients", message=str(exc))
		return
	for recipient in recipients:
		try:
			frappe.publish_realtime(event, payload, user=recipient, after_commit=False)
		except Exception as exc:
			frappe.log_error(
				title="FS Switch ESL listener publish",
				message=f"{recipient}: {exc}",
			)


def _tenant(context=None, domain=None) -> str:
	from fs_switch.call_setup import resolve_tenant

	return resolve_tenant(context=context, domain=domain)


def _context_from_queue(value) -> str:
	text = str(value or "").strip()
	return text.rsplit("@", 1)[1] if "@" in text else ""


def _user_for_agent(agent: str | None, tenant: str | None = None) -> str | None:
	import frappe

	extension = (agent or "").split("@", 1)[0]
	if not extension:
		return None
	filters = {"extension": extension}
	if tenant:
		filters["tenant"] = tenant
	return frappe.db.get_value("FS Extension", filters, "user")


def _event_domain(event: dict) -> str:
	domain = (
		event.get("variable_domain_name")
		or event.get("variable_sip_domain")
		or event.get("Domain-Name")
		or ""
	)
	if domain:
		return domain
	channel = str(event.get("Channel-Name") or "")
	if "@" in channel:
		return channel.rsplit("@", 1)[1].split("/", 1)[0]
	return ""


def _call_payload(event: dict) -> dict:
	name = event.get("Event-Name")
	context = (
		event.get("Caller-Context")
		or event.get("variable_user_context")
		or event.get("Channel-Context")
		or ""
	)
	tenant = _tenant(context=context, domain=_event_domain(event))
	return {
		"event": name,
		"uuid": event.get("Unique-ID"),
		"name": event.get("Channel-Name") or "",
		"direction": event.get("Call-Direction"),
		"from": event.get("Caller-Caller-ID-Number"),
		"from_name": event.get("Caller-Caller-ID-Name"),
		"to": event.get("Caller-Destination-Number"),
		"context": context,
		"callstate": event.get("Channel-Call-State") or "",
		"created": event.get("Event-Date-Timestamp") or "",
		"hangup_cause": event.get("Hangup-Cause"),
		"billsec": event.get("variable_billsec"),
		"queue": event.get("variable_cc_queue"),
		"tenant": tenant,
	}


def _agent_payload(event: dict) -> dict:
	agent = event.get("CC-Agent")
	queue = event.get("CC-Queue") or ""
	tenant = _tenant(context=_context_from_queue(queue) or _context_from_queue(agent))
	return {
		"action": event.get("CC-Action"),
		"agent": agent,
		"user": _user_for_agent(agent, tenant),
		"status": event.get("CC-Agent-Status"),
		"state": event.get("CC-Agent-State"),
		"queue": queue,
		"caller": event.get("CC-Member-CID-Number") or event.get("CC-Member-CID-Name"),
		"member_uuid": event.get("CC-Member-UUID"),
		"tenant": tenant,
	}


def _registration_payload(event: dict) -> dict:
	name = event.get("Event-Name")
	realm = event.get("realm") or event.get("reg_domain") or ""
	contact = event.get("contact") or event.get("reg_contact") or ""
	return {
		"action": "unregister" if name == "UNREGISTER" else "register",
		"registration": {
			"user": event.get("username") or event.get("reg_user") or "",
			"realm": realm,
			"contact": contact,
			"expires": event.get("expires") or event.get("reg_seconds") or "",
			"network_ip": event.get("network_ip") or "",
			"network_port": event.get("network_port") or "",
		},
		"tenant": _tenant(domain=realm),
	}


def _handle(event: dict):
	name = event.get("Event-Name")
	if name in CALL_EVENTS:
		_publish("fs_switch_call", _call_payload(event))
		return

	if name == "CUSTOM" and event.get("Event-Subclass") == "callcenter::info":
		if event.get("CC-Action") in AGENT_ACTIONS:
			# Publish Tenant-wide so a supervisor sees every queue in their
			# Tenant. The payload carries the owning user for direct notices.
			_publish("fs_switch_agent", _agent_payload(event))
		return

	if name in ("REGISTER", "UNREGISTER"):
		_publish("fs_switch_registration", _registration_payload(event))


def run(debug: bool = False):
	"""Reconnect forever; a FreeSWITCH restart must not stop the listener."""
	import frappe

	while True:
		try:
			settings = frappe.get_single("FS Switch Settings")
			with ESLConnection.from_settings(settings) as esl:
				esl.subscribe(EVENTS)
				if debug:
					print("FS Switch ESL listener connected")
				while True:
					event = esl.read_event()
					if event:
						if debug:
							print(event.get("Event-Name"), event.get("CC-Action", ""))
						try:
							_handle(event)
						except Exception as exc:
							# One bad event must not tear down the listener.
							frappe.log_error(
								title="FS Switch ESL listener event",
								message=str(exc),
							)
		except (OSError, ESLError, ConnectionError) as exc:
			frappe.log_error(title="FS Switch ESL listener", message=str(exc))
			if debug:
				print(f"FS Switch ESL listener error: {exc}")
			time.sleep(5)
		except Exception as exc:
			frappe.log_error(title="FS Switch ESL listener", message=str(exc))
			if debug:
				print(f"FS Switch ESL listener setup error: {exc}")
			time.sleep(5)
