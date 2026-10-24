"""Supervisor wallboard summary.

The wallboard is a projection of the same live snapshot the rest of the console
uses. Keeping the arithmetic pure makes queue depth and call-path rules testable
without a FreeSWITCH connection.
"""

from __future__ import annotations

from typing import Any


def _integer(value) -> int:
	try:
		return max(0, int(float(str(value or "0").replace(",", "").strip() or 0)))
	except (TypeError, ValueError):
		return 0


def _text(value) -> str:
	return str(value or "").strip()


def _queue_parts(value) -> tuple[str, str]:
	name = _text(value)
	if "@" not in name:
		return name, ""
	queue, context = name.rsplit("@", 1)
	return queue, context


def channel_path(channel: dict[str, Any]) -> str:
	"""Return a compact call path for a live channel."""
	caller = _text(channel.get("cid_num") or channel.get("cid_name")) or "Unknown"
	queue = _text(channel.get("queue") or channel.get("cc_queue"))
	agent = _text(channel.get("agent") or channel.get("cc_agent"))
	destination = _text(channel.get("dest") or channel.get("context")) or "unknown"
	if queue:
		parts = [caller, queue]
		if agent:
			parts.append(agent)
		return " \u2192 ".join(parts)
	return f"{caller} \u2192 {destination}"


def summarize(data: dict[str, Any] | None) -> dict[str, Any]:
	"""Build the wallboard cards, queue rows and call paths for one snapshot."""
	data = data or {}
	queues = []
	waiting = 0
	answered = 0
	abandoned = 0
	for row in data.get("queues") or []:
		name = _text(row.get("name"))
		queue, context = _queue_parts(name)
		queue_waiting = _integer(row.get("waiting"))
		queue_answered = _integer(row.get("calls_answered"))
		queue_abandoned = _integer(row.get("calls_abandoned"))
		waiting += queue_waiting
		answered += queue_answered
		abandoned += queue_abandoned
		queues.append(
			{
				"name": name,
				"queue": queue,
				"context": context,
				"waiting": queue_waiting,
				"answered": queue_answered,
				"abandoned": queue_abandoned,
				"max_wait_seconds": _integer(
					row.get("max_wait_time") or row.get("max_wait_seconds")
				),
			}
		)

	available = 0
	busy = 0
	on_break = 0
	logged_out = 0
	for row in data.get("agents") or []:
		status = _text(row.get("status"))
		state = _text(row.get("state"))
		if status == "Available" and state == "Waiting":
			available += 1
		elif status == "On Break":
			on_break += 1
		elif status == "Logged Out":
			logged_out += 1
		if state in ("Receiving", "In a queue call"):
			busy += 1

	calls = []
	longest_wait = 0
	seen_calls = set()
	for row in data.get("channels") or []:
		call_key = _text(row.get("call_uuid") or row.get("uuid"))
		if call_key and call_key in seen_calls:
			continue
		seen_calls.add(call_key)
		wait = _integer(row.get("wait_seconds"))
		longest_wait = max(longest_wait, wait)
		calls.append(
			{
				"uuid": _text(row.get("uuid")),
				"path": channel_path(row),
				"state": _text(row.get("callstate") or row.get("state")),
				"queue": _text(row.get("queue") or row.get("cc_queue")),
				"agent": _text(row.get("agent") or row.get("cc_agent")),
				"wait_seconds": wait,
			}
		)

	total_answered = answered + abandoned
	answer_rate = round((answered / total_answered) * 100) if total_answered else 0
	queue_calls = sum(1 for call in calls if call.get("queue"))
	return {
		"queues": queues,
		"calls": calls,
		"metrics": {
			"queue_count": len(queues),
			"waiting": waiting,
			"available_agents": available,
			"busy_agents": busy,
			"on_break": on_break,
			"logged_out": logged_out,
			"active_calls": len(calls),
			"queue_calls": queue_calls,
			"answered": answered,
			"abandoned": abandoned,
			"answer_rate": answer_rate,
			"longest_wait_seconds": longest_wait,
		},
	}
