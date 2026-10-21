"""Publish FreeSWITCH call and call-center events on Frappe's realtime channel.

Run next to the bench:

    bench --site <site> execute fs_switch.esl_listener.run

Events:
    fs_switch_call          a channel was created, answered or hung up
    fs_switch_agent         a call-center agent changed status or state
    fs_switch_registration  a SIP registration changed (reserved)
"""

from __future__ import annotations

import time

import frappe

from fs_switch.esl import ESLConnection, ESLError

EVENTS = "CHANNEL_CREATE CHANNEL_ANSWER CHANNEL_HANGUP_COMPLETE CUSTOM callcenter::info"


def _publish(event: str, payload: dict, user: str | None = None):
	frappe.publish_realtime(event, payload, user=user, after_commit=False)


def _user_for_agent(agent: str | None) -> str | None:
	extension = (agent or "").split("@", 1)[0]
	if not extension:
		return None
	return frappe.db.get_value("FS Extension", {"extension": extension}, "user")


def _handle(event: dict):
	name = event.get("Event-Name")
	if name in ("CHANNEL_CREATE", "CHANNEL_ANSWER", "CHANNEL_HANGUP_COMPLETE"):
		_publish(
			"fs_switch_call",
			{
				"event": name,
				"uuid": event.get("Unique-ID"),
				"direction": event.get("Call-Direction"),
				"from": event.get("Caller-Caller-ID-Number"),
				"from_name": event.get("Caller-Caller-ID-Name"),
				"to": event.get("Caller-Destination-Number"),
				"context": event.get("Caller-Context"),
				"hangup_cause": event.get("Hangup-Cause"),
				"billsec": event.get("variable_billsec"),
				"queue": event.get("variable_cc_queue"),
			},
		)
		return

	if name == "CUSTOM" and event.get("Event-Subclass") == "callcenter::info":
		action = event.get("CC-Action")
		if action in ("agent-status-change", "agent-state-change", "agent-offering"):
			agent = event.get("CC-Agent")
			_publish(
				"fs_switch_agent",
				{
					"action": action,
					"agent": agent,
					"status": event.get("CC-Agent-Status"),
					"state": event.get("CC-Agent-State"),
					"queue": event.get("CC-Queue"),
					"caller": event.get("CC-Member-CID-Number") or event.get("CC-Member-CID-Name"),
					"member_uuid": event.get("CC-Member-UUID"),
				},
				user=_user_for_agent(agent),
			)


def run(debug: bool = False):
	"""Reconnect forever; a FreeSWITCH restart must not stop the listener."""
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
						_handle(event)
		except (OSError, ESLError, ConnectionError) as exc:
			frappe.log_error(title="FS Switch ESL listener", message=str(exc))
			if debug:
				print(f"FS Switch ESL listener error: {exc}")
			time.sleep(5)
