"""Small, dependency-free FreeSWITCH Event Socket Layer client.

Frappe already runs on the same host/network as FreeSWITCH in the supported
deployments, so a raw socket is enough. Keeping this module free of a third-party
ESL package makes the app easier to install and audit.
"""

from __future__ import annotations

import json
import socket
import time
from urllib.parse import unquote


class ESLError(RuntimeError):
	"""A connection or command failed."""


class ESLConnection:
	def __init__(self, host: str, port: int, password: str, timeout: float = 5.0):
		self.sock = socket.create_connection((host, int(port)), timeout=timeout)
		self.file = self.sock.makefile("rb")
		self._read_block()  # auth/request
		reply = self._command(f"auth {password}")
		if "+OK" not in reply:
			self.close()
			raise ESLError(f"ESL authentication failed: {reply or 'no reply'}")

	@classmethod
	def from_settings(cls, settings=None):
		if settings is None:
			import frappe

			settings = frappe.get_single("FS Switch Settings")
		return cls(
			settings.esl_host or "127.0.0.1",
			int(settings.esl_port or 8021),
			settings.get_password("esl_password", raise_exception=False) or "",
		)

	def _read_block(self):
		headers = {}
		while True:
			line = self.file.readline()
			if not line:
				raise ESLError("The ESL connection closed.")
			line = line.decode("utf-8", "replace").rstrip("\r\n")
			if line == "":
				break
			if ": " in line:
				key, value = line.split(": ", 1)
				headers[key] = value
		length = int(headers.get("Content-Length", "0") or 0)
		body = self.file.read(length) if length else b""
		return headers, body

	def _send(self, command: str):
		self.sock.sendall((command + "\n\n").encode("utf-8"))

	def _command(self, command: str) -> str:
		self._send(command)
		headers, _ = self._read_block()
		return headers.get("Reply-Text", "")

	def api(self, command: str) -> str:
		"""Run one FreeSWITCH API command and return the response body."""
		self._send(f"api {command}")
		_, body = self._read_block()
		return body.decode("utf-8", "replace").strip()

	def subscribe(self, events: str):
		reply = self._command(f"event plain {events}")
		if "+OK" not in reply:
			raise ESLError(f"Could not subscribe to ESL events: {reply}")

	def read_event(self) -> dict:
		headers, body = self._read_block()
		if headers.get("Content-Type") != "text/event-plain":
			return {}
		event = {}
		for line in body.decode("utf-8", "replace").split("\n"):
			if ": " in line:
				key, value = line.split(": ", 1)
				event[key] = unquote(value)
		return event

	def close(self):
		try:
			self.file.close()
		finally:
			self.sock.close()

	def __enter__(self):
		return self

	def __exit__(self, *_):
		self.close()


def _rows(text: str) -> list[dict]:
	try:
		data = json.loads(text or "{}")
	except ValueError:
		return []
	if isinstance(data, dict):
		rows = data.get("rows")
		return rows if isinstance(rows, list) else []
	return data if isinstance(data, list) else []


def _callcenter_rows(text: str) -> list[dict]:
	"""Turn callcenter_config list output into rows with named fields.

	FreeSWITCH emits a header row followed by pipe-separated data. Older
	versions can omit the header, so fall back to the historical first-three
	columns in that case.
	"""
	rows = []
	header = []
	for line in (text or "").splitlines():
		line = line.strip()
		if not line or line.startswith("+OK") or line.startswith("-ERR"):
			continue
		parts = [part.strip() for part in line.split("|")]
		if parts and parts[0].lower() == "name":
			header = [part.lower().replace("-", "_") for part in parts]
			continue
		row = {"name": parts[0] if parts else line, "raw": line}
		if header:
			row.update({key: value for key, value in zip(header, parts) if key})
			row["name"] = row.get("name") or (parts[0] if parts else line)
		else:
			if len(parts) > 1:
				row["status"] = parts[1]
			if len(parts) > 2:
				row["state"] = parts[2]
		rows.append(row)
	return rows


def _wait_seconds(row: dict) -> int:
	joined = row.get("cc_queue_joined_epoch") or row.get("variable_cc_queue_joined_epoch")
	try:
		return max(0, int(time.time() - float(joined)))
	except (TypeError, ValueError):
		return 0


def _channel_row(row: dict) -> dict:
	return {
		"uuid": row.get("uuid") or row.get("Unique-ID") or "",
		"call_uuid": row.get("call_uuid") or "",
		"name": row.get("name") or "",
		"cid_name": row.get("cid_name") or "",
		"cid_num": row.get("cid_num") or "",
		"dest": row.get("dest") or "",
		"context": row.get("context") or "",
		"application": row.get("application") or "",
		"queue": row.get("cc_queue") or row.get("variable_cc_queue") or "",
		"agent": row.get("cc_agent") or row.get("variable_cc_agent") or "",
		"wait_seconds": _wait_seconds(row),
		"callstate": row.get("callstate") or row.get("state") or "",
		"created": row.get("created") or "",
		"raw": row,
	}


def _registration_row(row: dict) -> dict:
	return {
		"user": row.get("user") or row.get("reg_user") or "",
		"realm": row.get("realm") or row.get("reg_domain") or "",
		"contact": row.get("contact") or "",
		"expires": row.get("expires") or row.get("reg_seconds") or "",
		"network_ip": row.get("network_ip") or "",
		"network_port": row.get("network_port") or "",
		"raw": row,
	}


def _enrich_queue_channel(esl, channel: dict) -> None:
	"""Resolve queue and wait metadata for a callcenter call or bridge leg."""
	if channel.get("queue") or channel.get("application") not in (
		"callcenter",
		"uuid_bridge",
	):
		return
	uuid = channel.get("uuid")
	if not uuid:
		return
	try:
		queue = esl.api(f"uuid_getvar {uuid} cc_queue").strip()
		if not queue or queue == "_undef_":
			return
		channel["queue"] = queue
		joined = esl.api(f"uuid_getvar {uuid} cc_queue_joined_epoch").strip()
		channel["wait_seconds"] = _wait_seconds({"cc_queue_joined_epoch": joined})
		agent = esl.api(f"uuid_getvar {uuid} cc_agent").strip()
		if agent and agent != "_undef_":
			channel["agent"] = agent
	except (OSError, ESLError):
		return


def live_data(settings=None) -> dict:
	"""Read the current channels, registrations, agents and queues.

	The endpoint returns a useful structure even when FreeSWITCH is down, so the
	console can show a clear connection error instead of a blank table.
	"""
	try:
		with ESLConnection.from_settings(settings) as esl:
			channels = [_channel_row(row) for row in _rows(esl.api("show channels as json"))]
			for channel in channels:
				_enrich_queue_channel(esl, channel)
			registrations = [
				_registration_row(row) for row in _rows(esl.api("show registrations as json"))
			]
			agents = _callcenter_rows(esl.api("callcenter_config agent list"))
			queues = _callcenter_rows(esl.api("callcenter_config queue list"))
			queue_counts = {}
			for channel in channels:
				if channel.get("application") != "callcenter":
					continue
				queue_name = str(channel.get("queue") or "").strip()
				if queue_name:
					queue_counts[queue_name] = queue_counts.get(queue_name, 0) + 1
			for queue in queues:
				queue["waiting"] = queue_counts.get(str(queue.get("name") or ""), 0)
		return {
			"ok": True,
			"channels": channels,
			"registrations": registrations,
			"agents": agents,
			"queues": queues,
			"error": None,
		}
	except (OSError, ESLError) as exc:
		return {
			"ok": False,
			"channels": [],
			"registrations": [],
			"agents": [],
			"queues": [],
			"error": str(exc),
		}


def run_action(action: str, **kwargs) -> str:
	"""Execute a small, explicit set of live actions.

	Arbitrary ESL commands are deliberately not exposed to the browser.
	"""
	allowed = {"hangup", "transfer", "answer", "hold", "agent_status", "reload"}
	if action not in allowed:
		raise ValueError(f"Unsupported action: {action}")

	with ESLConnection.from_settings() as esl:
		if action == "hangup":
			return esl.api(f"uuid_kill {_required(kwargs, 'uuid')}")
		if action == "transfer":
			return esl.api(
				f"uuid_transfer {_required(kwargs, 'uuid')} "
				f"{_required(kwargs, 'destination')} XML {_required(kwargs, 'context')}"
			)
		if action == "answer":
			return esl.api(f"uuid_answer {_required(kwargs, 'uuid')}")
		if action == "hold":
			return esl.api(f"uuid_hold {_required(kwargs, 'uuid')}")
		if action == "agent_status":
			status = _required(kwargs, "status")
			if status not in ("Logged Out", "Available", "On Break"):
				raise ValueError(f"Unsupported agent status: {status}")
			return esl.api(
				"callcenter_config agent set status "
				f"{_required(kwargs, 'agent')} '{status}'"
			)
		return esl.api("reloadxml")


def _required(values: dict, key: str) -> str:
	value = str(values.get(key) or "").strip()
	if not value:
		raise ValueError(f"{key} is required")
	return value
