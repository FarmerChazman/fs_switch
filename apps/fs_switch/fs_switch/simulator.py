"""Walk a semantic Flow with call inputs and return the node path.

The simulator reads the Flow graph, never the compiled XML. It exists so an
administrator can answer "what happens if a call reaches this Flow at 14:30 and
presses 2?" before publishing, and so the publish checklist has a route path to
attach.

Inputs are deliberately small:

- ``destination``: the dialed number, used for menu/time fields and the Flow's
  destination pattern;
- ``at``: a simulated clock for ``${strftime(...)}`` fields;
- ``digits``: the digits a caller types, consumed in order by menus;
- ``variables``: initial channel variables for time conditions.

Time fields support ``destination_number``, ``${destination_number}``,
``${strftime(FORMAT)}`` and variables set earlier in the Flow. An unsupported
field is an error rather than a guess: a simulator that silently chooses a
branch is worse than one that says it cannot know.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, time
from typing import Any

from fs_switch.flow import FlowError, NODE_SPECS, load_flow, validate_flow

DEFAULT_MAX_STEPS = 50
MAX_STEPS_LIMIT = 500


class SimulationError(ValueError):
	"""Raised when the Flow cannot be walked with the supplied inputs."""


def simulate_flow(
	flow: Any,
	*,
	destination: Any = None,
	at: Any = None,
	digits: Any = None,
	variables: Any = None,
	destination_number: Any = None,
	max_steps: int = DEFAULT_MAX_STEPS,
) -> dict[str, Any]:
	"""Return the path a call takes through a semantic Flow.

	Bad Flow structure is returned as ``valid: false`` with ``errors``. Bad call
	inputs (an unparseable ``at`` or step limit) raise ``ValueError``.
	"""
	now = _parse_at(at)
	max_steps = _parse_max_steps(max_steps)
	destination_text = str(destination or "").strip()
	pattern = str(destination_number or "").strip()
	initial_variables = _load_variables(variables)

	try:
		graph = load_flow(flow)
	except FlowError as exc:
		return _invalid([str(exc)], destination_text, now)

	errors = validate_flow(graph)
	if errors:
		return _invalid(errors, destination_text, now)

	if pattern and destination_text:
		try:
			matched = bool(re.search(pattern, destination_text))
		except re.error as exc:
			return _invalid(
				[f"destination_number is not a valid regular expression: {exc}"],
				destination_text,
				now,
			)
		if not matched:
			return _no_match(pattern, destination_text, initial_variables, now)

	nodes: list[dict[str, Any]] = graph["nodes"]
	by_id = {str(node["id"]): node for node in nodes}
	targets: dict[str, dict[str, str]] = {}
	for edge in graph["edges"]:
		source = str(edge["source"])
		handle = str(edge.get("sourceHandle") or "next").strip() or "next"
		targets.setdefault(source, {})[handle] = str(edge["target"])

	node_id = str(graph["entry"])
	path: list[dict[str, Any]] = []
	state = dict(initial_variables)
	cursor = 0

	for _ in range(max_steps):
		node = by_id.get(node_id)
		if node is None:
			return _invalid(
				[f"The simulator reached missing node {node_id!r}."],
				destination_text,
				now,
				path,
				state,
			)
		node_type = str(node.get("type") or "").strip().lower()
		spec = NODE_SPECS.get(node_type)
		if spec is None:
			return _invalid(
				[f"Node {node_id!r} has unknown type {node_type!r}."],
				destination_text,
				now,
				path,
				state,
			)
		data = node.get("data") or {}
		record = {
			"node": node_id,
			"type": node_type,
			"label": str(data.get("label") or spec.label),
			"port": None,
			"note": "",
		}
		path.append(record)

		if spec.terminal:
			return _ok(
				path,
				state,
				destination_text,
				now,
				terminal=node_id,
				outcome=record["label"],
			)

		try:
			if node_type == "menu":
				port, note, cursor = _simulate_menu(
					spec, data, str(digits or ""), cursor, state
				)
			elif node_type == "time":
				port, note = _simulate_time(
					node_id, data, destination_text, now, state
				)
			elif node_type == "set":
				port, note = _simulate_set(data, destination_text, state, now)
			else:
				port, note = "next", ""
		except SimulationError as exc:
			return _invalid(
				[str(exc)],
				destination_text,
				now,
				path,
				state,
			)

		record["port"] = port
		record["note"] = note
		target = targets.get(node_id, {}).get(port)
		if target is None:
			return _invalid(
				[f"Node {node_id!r} has no edge for output {port!r}."],
				destination_text,
				now,
				path,
				state,
			)
		node_id = target

	return _ok(
		path,
		state,
		destination_text,
		now,
		terminal=None,
		outcome=None,
		warnings=[f"Stopped after {max_steps} steps; the flow may loop."],
		truncated=True,
	)


def _simulate_menu(spec, data, digits, cursor, variables):
	try:
		handles = spec.output_handles(data)
	except FlowError as exc:
		raise SimulationError(str(exc)) from exc
	allowed = {handle.split(":", 1)[1] for handle in handles if handle.startswith("digit:")}
	tries = _integer(data, "tries", 1, 1)

	chosen = ""
	consumed: list[str] = []
	for _ in range(tries):
		if cursor >= len(digits):
			break
		digit = digits[cursor]
		cursor += 1
		consumed.append(digit)
		if digit in allowed:
			chosen = digit
			break

	variable = str(data.get("variable") or "menu_digit").strip() or "menu_digit"
	variables[variable] = chosen

	if chosen:
		label = _option_label(data, chosen)
		note = f"digit {chosen}" + (f" ({label})" if label else "")
		return f"digit:{chosen}", note, cursor
	if consumed:
		return "timeout", f"no valid digit (tried {''.join(consumed)})", cursor
	return "timeout", "no digit entered", cursor


def _simulate_time(node_id, data, destination, now, variables):
	field_name = str(data.get("field") or "${strftime(%H%M)}").strip()
	expression = str(data.get("expression") or "").strip()
	if not expression:
		raise SimulationError("time.expression is required.")
	value = _resolve_field(field_name, destination, now, variables)
	if value is None:
		raise SimulationError(
			f"Cannot simulate time node {node_id!r}: field {field_name!r} is not available."
		)
	try:
		matched = bool(re.search(expression, value))
	except re.error as exc:
		raise SimulationError(
			f"time.expression is not a valid regular expression: {exc}"
		) from exc
	port = "match" if matched else "no_match"
	note = (
		f"{field_name} = {value!r} "
		f"{'matches' if matched else 'does not match'} {expression!r}"
	)
	return port, note


def _simulate_set(data, destination, variables, now):
	variable = str(data.get("variable") or "").strip()
	if not variable:
		raise SimulationError("set.variable is required.")
	value = _expand(data.get("value") or "", destination, variables, now)
	variables[variable] = value
	return "next", f"{variable}={value}"


def _resolve_field(field_name: str, destination: str, now: datetime, variables: dict[str, str]):
	name = field_name.strip()
	if name in ("destination_number", "${destination_number}"):
		return destination
	match = re.fullmatch(r"\$\{strftime\((.+)\)\}", name)
	if match:
		try:
			return now.strftime(match.group(1))
		except ValueError as exc:
			raise SimulationError(
				f"Unsupported strftime format {match.group(1)!r}: {exc}"
			) from exc
	match = re.fullmatch(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", name)
	if match:
		key = match.group(1)
		return str(variables[key]) if key in variables else None
	if name in variables:
		return str(variables[name])
	return None


def _expand(value: Any, destination: str, variables: dict[str, str], now: datetime) -> str:
	text = str(value).replace("${destination_number}", destination)

	def replace(match):
		token = match.group(1).strip()
		strftime = re.fullmatch(r"strftime\((.+)\)", token)
		if strftime:
			try:
				return now.strftime(strftime.group(1))
			except ValueError as exc:
				raise SimulationError(
					f"Unsupported strftime format {strftime.group(1)!r}: {exc}"
				) from exc
		return str(variables.get(token, ""))

	return re.sub(r"\$\{([^{}]+)\}", replace, text)


def _option_label(data: dict[str, Any], digit: str) -> str:
	for option in data.get("options") or []:
		if isinstance(option, dict) and str(option.get("digit") or "").strip() == digit:
			return str(option.get("label") or "").strip()
	return ""


def _integer(data: dict[str, Any], key: str, default: int, minimum: int) -> int:
	value = data.get(key, default)
	try:
		number = int(value)
	except (TypeError, ValueError) as exc:
		raise SimulationError(f"{key} must be an integer.") from exc
	if number < minimum:
		raise SimulationError(f"{key} must be at least {minimum}.")
	return number


def _parse_at(value: Any) -> datetime:
	if value is None:
		return datetime.now()
	if isinstance(value, datetime):
		return value
	if isinstance(value, date):
		return datetime.combine(value, time())
	if isinstance(value, time):
		return datetime.combine(date.today(), value)
	text = str(value).strip()
	if not text:
		return datetime.now()
	try:
		if re.fullmatch(r"\d{4}", text):
			return datetime.combine(date.today(), time(int(text[:2]), int(text[2:])))
		if re.fullmatch(r"\d{1,2}:\d{2}", text):
			hour, minute = (int(part) for part in text.split(":"))
			return datetime.combine(date.today(), time(hour, minute))
		return datetime.fromisoformat(text)
	except ValueError as exc:
		raise ValueError(
			f"at must be an ISO datetime, HH:MM or HHMM: {exc}"
		) from exc


def _parse_max_steps(value: Any) -> int:
	try:
		number = int(value)
	except (TypeError, ValueError) as exc:
		raise ValueError("max_steps must be an integer.") from exc
	if number < 1 or number > MAX_STEPS_LIMIT:
		raise ValueError(f"max_steps must be between 1 and {MAX_STEPS_LIMIT}.")
	return number


def _load_variables(value: Any) -> dict[str, str]:
	if value is None or value == "":
		return {}
	if isinstance(value, str):
		try:
			value = json.loads(value)
		except ValueError as exc:
			raise ValueError(f"variables must be a JSON object: {exc}") from exc
	if not isinstance(value, dict):
		raise ValueError("variables must be a JSON object.")
	return {str(key): str(item) for key, item in value.items()}


def _ok(
	path,
	variables,
	destination,
	now,
	*,
	terminal,
	outcome,
	warnings=None,
	truncated=False,
):
	return {
		"valid": True,
		"matched": True,
		"path": path,
		"terminal": terminal,
		"outcome": outcome,
		"variables": variables,
		"warnings": warnings or [],
		"errors": [],
		"truncated": truncated,
		"destination": destination,
		"at": now.isoformat(timespec="seconds"),
	}


def _no_match(pattern, destination, variables, now):
	return {
		"valid": True,
		"matched": False,
		"path": [],
		"terminal": None,
		"outcome": None,
		"variables": variables,
		"warnings": [
			f"Destination {destination!r} does not match {pattern!r}."
		],
		"errors": [],
		"truncated": False,
		"destination": destination,
		"at": now.isoformat(timespec="seconds"),
	}


def _invalid(errors, destination, now, path=None, variables=None):
	return {
		"valid": False,
		"matched": False,
		"path": path or [],
		"terminal": None,
		"outcome": None,
		"variables": variables or {},
		"warnings": [],
		"errors": list(errors),
		"truncated": False,
		"destination": destination,
		"at": now.isoformat(timespec="seconds"),
	}
