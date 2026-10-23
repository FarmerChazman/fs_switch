"""Semantic call-flow model and compiler for FS Switch.

The raw dialplan editor stores FreeSWITCH applications in a graph. That is a
useful escape hatch, but it is not the product model: a telecom administrator
should describe intent ("play the menu, route 1 to sales") and let the server
choose the FreeSWITCH actions.

This module defines that intent-level model and compiles it into a small state
machine of named FreeSWITCH extensions. Each semantic node becomes one
extension or a small group of branch-selector extensions; edges become
transfers to the next extension. The extension names are deterministic, which
makes the generated XML readable and makes a later publish/diff/rollback
feature possible.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable
from xml.sax.saxutils import quoteattr

SCHEMA_VERSION = 1


class FlowError(ValueError):
	"""Raised when a semantic flow cannot be validated or compiled."""


@dataclass(frozen=True)
class Branch:
	"""One outgoing condition from a semantic node."""

	handle: str
	field: str
	expression: str


@dataclass
class RenderedNode:
	"""The FreeSWITCH actions and branches produced by one semantic node."""

	actions: list[tuple[str, str | None]] = field(default_factory=list)
	branches: list[Branch] = field(default_factory=list)


@dataclass(frozen=True)
class NodeSpec:
	"""Definition of a semantic node type."""

	type: str
	label: str
	category: str
	outputs: tuple[str, ...] = ("next",)
	required: tuple[str, ...] = ()
	terminal: bool = False
	defaults: dict[str, Any] = field(default_factory=dict)
	render: Callable[[dict[str, Any], str], RenderedNode] = None  # type: ignore[assignment]
	validate_data: Callable[[dict[str, Any]], list[str]] | None = None
	dynamic_outputs: Callable[[dict[str, Any]], tuple[str, ...]] | None = None

	def output_handles(self, data: dict[str, Any]) -> tuple[str, ...]:
		if self.dynamic_outputs:
			return self.dynamic_outputs(data)
		return self.outputs


def _text(data: dict[str, Any], key: str, default: str = "") -> str:
	value = data.get(key)
	if value is None:
		return default
	return str(value).strip()


def _empty(value: Any) -> bool:
	if value is None:
		return True
	if isinstance(value, str):
		return not value.strip()
	if isinstance(value, (list, tuple, dict)):
		return not value
	return False


def _path(data: dict[str, Any], key: str, default: str = "") -> str:
	value = _text(data, key, default)
	if not value:
		raise FlowError(f"{key} is required.")
	if any(character.isspace() for character in value):
		raise FlowError(f"{key} must not contain spaces: {value!r}.")
	return value


def _integer(data: dict[str, Any], key: str, default: int, minimum: int = 0) -> int:
	value = data.get(key, default)
	try:
		number = int(value)
	except (TypeError, ValueError) as exc:
		raise FlowError(f"{key} must be an integer.") from exc
	if number < minimum:
		raise FlowError(f"{key} must be at least {minimum}.")
	return number


def _option_digit(option: Any, index: int) -> str:
	if isinstance(option, str):
		digit = option.strip()
	elif isinstance(option, dict):
		digit = str(option.get("digit") or "").strip()
	else:
		raise FlowError(f"options[{index}] must be a digit or an object with a digit.")
	if not re.fullmatch(r"[0-9]", digit):
		raise FlowError(f"options[{index}] must be a single digit from 0 to 9.")
	return digit


def _menu_digits(data: dict[str, Any]) -> list[str]:
	options = data.get("options")
	if not isinstance(options, list) or not options:
		raise FlowError("menu.options must contain at least one digit.")
	digits: list[str] = []
	for index, option in enumerate(options):
		digit = _option_digit(option, index)
		if digit in digits:
			raise FlowError(f"menu.options contains the digit {digit!r} more than once.")
		digits.append(digit)
	return digits


def _validate_menu(data: dict[str, Any]) -> list[str]:
	errors: list[str] = []
	try:
		_menu_digits(data)
	except FlowError as exc:
		errors.append(str(exc))
	try:
		_path(data, "prompt")
	except FlowError as exc:
		errors.append(str(exc))
	invalid_prompt = (
		_text(data, "invalid_prompt") or "ivr/ivr-that_was_an_invalid_entry.wav"
	)
	if any(character.isspace() for character in invalid_prompt):
		errors.append("menu.invalid_prompt must not contain spaces.")
	variable = _text(data, "variable") or "menu_digit"
	if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", variable):
		errors.append("menu.variable must be a valid FreeSWITCH variable name.")
	for key, default, minimum in (
		("min_digits", 1, 1),
		("max_digits", 1, 1),
		("tries", 1, 1),
		("timeout_ms", 5000, 1),
	):
		try:
			_integer(data, key, default, minimum)
		except FlowError as exc:
			errors.append(str(exc))
	try:
		minimum = _integer(data, "min_digits", 1, 1)
		maximum = _integer(data, "max_digits", 1, 1)
		if minimum > maximum:
			errors.append("menu.min_digits must not be greater than menu.max_digits.")
		elif minimum != 1 or maximum != 1:
			errors.append(
				"menu digit branches require min_digits and max_digits to be 1."
			)
	except FlowError:
		pass
	terminators = _text(data, "terminators", "#")
	if not terminators:
		errors.append("menu.terminators must not be empty.")
	return errors


def _menu_outputs(data: dict[str, Any]) -> tuple[str, ...]:
	return tuple(f"digit:{digit}" for digit in _menu_digits(data)) + ("timeout",)


def _render_answer(data: dict[str, Any], context: str) -> RenderedNode:
	return RenderedNode(actions=[("answer", None)])


def _render_play(data: dict[str, Any], context: str) -> RenderedNode:
	return RenderedNode(actions=[("playback", _path(data, "prompt"))])


def _render_menu(data: dict[str, Any], context: str) -> RenderedNode:
	errors = _validate_menu(data)
	if errors:
		raise FlowError("; ".join(errors))
	digits = _menu_digits(data)
	prompt = _path(data, "prompt")
	invalid_prompt = (
		_text(data, "invalid_prompt") or "ivr/ivr-that_was_an_invalid_entry.wav"
	)
	variable = _text(data, "variable") or "menu_digit"
	minimum = _integer(data, "min_digits", 1, 1)
	maximum = _integer(data, "max_digits", 1, 1)
	tries = _integer(data, "tries", 1, 1)
	timeout = _integer(data, "timeout_ms", 5000, 1)
	terminators = _text(data, "terminators", "#")
	regexp = "[" + "".join(digits) + "]"
	action_data = (
		f"{minimum} {maximum} {tries} {timeout} {terminators} "
		f"{prompt} {invalid_prompt} {variable} {regexp}"
	)
	return RenderedNode(
		actions=[("set", f"{variable}="), ("play_and_get_digits", action_data)],
		branches=[
			*[Branch(f"digit:{digit}", f"${{{variable}}}", f"^{digit}$") for digit in digits],
			Branch("timeout", f"${{{variable}}}", "^$"),
		],
	)


def _render_time(data: dict[str, Any], context: str) -> RenderedNode:
	field_name = _text(data, "field") or "${strftime(%H%M)}"
	expression = _text(data, "expression")
	if not expression:
		raise FlowError("time.expression is required.")
	return RenderedNode(
		branches=[
			Branch("match", field_name, expression),
			Branch("no_match", field_name, "^.*$"),
		]
	)


def _render_set(data: dict[str, Any], context: str) -> RenderedNode:
	variable = _text(data, "variable")
	value = _text(data, "value")
	if not variable:
		raise FlowError("set.variable is required.")
	return RenderedNode(actions=[("set", f"{variable}={value}")])


def _render_sleep(data: dict[str, Any], context: str) -> RenderedNode:
	milliseconds = _integer(data, "milliseconds", 1000, 1)
	return RenderedNode(actions=[("sleep", str(milliseconds))])


def _render_record(data: dict[str, Any], context: str) -> RenderedNode:
	path = _path(data, "path")
	return RenderedNode(actions=[("record_session", path)])


def _endpoint(value: Any) -> str:
	endpoint = str(value or "").strip()
	if not endpoint:
		raise FlowError("ring_group.endpoints must not contain an empty endpoint.")
	if "/" in endpoint or endpoint.startswith("${"):
		return endpoint
	return f"user/{endpoint}@${{domain_name}}"


def _render_ring_group(data: dict[str, Any], context: str) -> RenderedNode:
	endpoints = data.get("endpoints")
	if isinstance(endpoints, str):
		endpoints = [endpoint.strip() for endpoint in endpoints.split(",") if endpoint.strip()]
	if not isinstance(endpoints, list) or not endpoints:
		raise FlowError("ring_group.endpoints must contain at least one endpoint.")
	dial_string = ",".join(_endpoint(endpoint) for endpoint in endpoints)
	timeout = data.get("timeout_seconds", 30)
	if timeout not in (None, "", 0):
		seconds = _integer(data, "timeout_seconds", 30, 1)
		dial_string = f"{{leg_timeout={seconds}}}{dial_string}"
	return RenderedNode(actions=[("bridge", dial_string)])


def _render_queue(data: dict[str, Any], context: str) -> RenderedNode:
	queue = _text(data, "queue")
	if not queue:
		raise FlowError("queue.queue is required.")
	if "@" not in queue:
		queue = f"{queue}@{_text(data, 'context') or context}"
	return RenderedNode(actions=[("callcenter", queue)])


def _render_voicemail(data: dict[str, Any], context: str) -> RenderedNode:
	profile = _text(data, "profile") or "default"
	domain = _text(data, "domain") or "${domain_name}"
	mailbox = _text(data, "mailbox")
	if not mailbox:
		raise FlowError("voicemail.mailbox is required.")
	return RenderedNode(actions=[("voicemail", f"{profile} {domain} {mailbox}")])


def _render_transfer(data: dict[str, Any], context: str) -> RenderedNode:
	destination = _text(data, "destination")
	if not destination:
		raise FlowError("transfer.destination is required.")
	dialplan = _text(data, "dialplan") or "XML"
	target_context = _text(data, "context") or context
	return RenderedNode(actions=[("transfer", f"{destination} {dialplan} {target_context}")])


def _render_conference(data: dict[str, Any], context: str) -> RenderedNode:
	room = _text(data, "room")
	profile = _text(data, "profile") or "default"
	if not room:
		raise FlowError("conference.room is required.")
	target = room if "@" in room else f"{room}@{profile}"
	return RenderedNode(actions=[("conference", target)])


def _render_park(data: dict[str, Any], context: str) -> RenderedNode:
	return RenderedNode(actions=[("park", None)])


def _render_hangup(data: dict[str, Any], context: str) -> RenderedNode:
	cause = _text(data, "cause")
	return RenderedNode(actions=[("hangup", cause or None)])


def _validate_endpoints(data: dict[str, Any]) -> list[str]:
	endpoints = data.get("endpoints")
	if isinstance(endpoints, str):
		endpoints = [endpoint.strip() for endpoint in endpoints.split(",") if endpoint.strip()]
	if not isinstance(endpoints, list) or not endpoints:
		return ["ring_group.endpoints must contain at least one endpoint."]
	try:
		for endpoint in endpoints:
			_endpoint(endpoint)
	except FlowError as exc:
		return [str(exc)]
	if data.get("timeout_seconds") not in (None, "", 0):
		try:
			_integer(data, "timeout_seconds", 30, 1)
		except FlowError as exc:
			return [str(exc)]
	return []


def _validate_time(data: dict[str, Any]) -> list[str]:
	if not _text(data, "expression"):
		return ["time.expression is required."]
	return []


def _validate_sleep(data: dict[str, Any]) -> list[str]:
	try:
		_integer(data, "milliseconds", 1000, 1)
	except FlowError as exc:
		return [str(exc)]
	return []


NODE_SPECS: dict[str, NodeSpec] = {
	"answer": NodeSpec("answer", "Answer", "Call control", render=_render_answer),
	"play": NodeSpec(
		"play",
		"Play prompt",
		"Media",
		required=("prompt",),
		defaults={"prompt": ""},
		render=_render_play,
	),
	"menu": NodeSpec(
		"menu",
		"IVR menu",
		"Routing",
		required=("prompt", "options"),
		defaults={
			"prompt": "",
			"invalid_prompt": "ivr/ivr-that_was_an_invalid_entry.wav",
			"variable": "menu_digit",
			"min_digits": 1,
			"max_digits": 1,
			"tries": 1,
			"timeout_ms": 5000,
			"terminators": "#",
			"options": [],
		},
		render=_render_menu,
		validate_data=_validate_menu,
		dynamic_outputs=_menu_outputs,
	),
	"time": NodeSpec(
		"time",
		"Time condition",
		"Routing",
		outputs=("match", "no_match"),
		required=("expression",),
		defaults={"field": "${strftime(%H%M)}", "expression": ""},
		render=_render_time,
		validate_data=_validate_time,
	),
	"ring_group": NodeSpec(
		"ring_group",
		"Ring group",
		"Routing",
		required=("endpoints",),
		defaults={"endpoints": [], "timeout_seconds": 30},
		render=_render_ring_group,
		validate_data=_validate_endpoints,
	),
	"queue": NodeSpec(
		"queue",
		"Call-center queue",
		"Routing",
		required=("queue",),
		defaults={"queue": ""},
		render=_render_queue,
	),
	"voicemail": NodeSpec(
		"voicemail",
		"Voicemail",
		"Routing",
		outputs=(),
		terminal=True,
		required=("mailbox",),
		defaults={"profile": "default", "domain": "${domain_name}", "mailbox": ""},
		render=_render_voicemail,
	),
	"transfer": NodeSpec(
		"transfer",
		"Transfer",
		"Call control",
		outputs=(),
		terminal=True,
		required=("destination",),
		defaults={"destination": "", "dialplan": "XML", "context": ""},
		render=_render_transfer,
	),
	"conference": NodeSpec(
		"conference",
		"Conference",
		"Media",
		outputs=(),
		terminal=True,
		required=("room",),
		defaults={"room": "", "profile": "default"},
		render=_render_conference,
	),
	"park": NodeSpec(
		"park",
		"Park",
		"Call control",
		outputs=(),
		terminal=True,
		render=_render_park,
	),
	"hangup": NodeSpec(
		"hangup",
		"Hang up",
		"Call control",
		outputs=(),
		terminal=True,
		defaults={"cause": ""},
		render=_render_hangup,
	),
	"set": NodeSpec(
		"set",
		"Set variable",
		"Variables",
		required=("variable",),
		defaults={"variable": "", "value": ""},
		render=_render_set,
	),
	"sleep": NodeSpec(
		"sleep",
		"Sleep",
		"Call control",
		defaults={"milliseconds": 1000},
		render=_render_sleep,
		validate_data=_validate_sleep,
	),
	"record": NodeSpec(
		"record",
		"Record call",
		"Media",
		required=("path",),
		defaults={"path": ""},
		render=_render_record,
	),
}


def node_catalog() -> list[dict[str, Any]]:
	"""Return a JSON-safe description of the semantic node palette."""
	catalog = []
	for spec in NODE_SPECS.values():
		outputs = list(spec.outputs)
		if spec.dynamic_outputs:
			outputs = ["digit:<digit>", "timeout"]
		catalog.append(
			{
				"type": spec.type,
				"label": spec.label,
				"category": spec.category,
				"outputs": outputs,
				"required": list(spec.required),
				"terminal": spec.terminal,
				"defaults": copy.deepcopy(spec.defaults),
			}
		)
	return catalog


def load_flow(flow: Any) -> dict[str, Any]:
	"""Accept a dict, JSON string, or a DocType-like object with a graph."""
	if hasattr(flow, "graph"):
		flow = flow.graph
	if isinstance(flow, str):
		try:
			flow = json.loads(flow)
		except ValueError as exc:
			raise FlowError(f"The flow is not valid JSON: {exc}") from exc
	if not isinstance(flow, dict):
		raise FlowError("The flow must be a JSON object.")
	return flow


def _validate_required(node_id: str, spec: NodeSpec, data: dict[str, Any]) -> list[str]:
	errors = []
	for key in spec.required:
		if _empty(data.get(key)):
			errors.append(f"Node {node_id!r} ({spec.type}) requires {key!r}.")
	return errors


def validate_flow(flow: Any) -> list[str]:
	"""Return every structural problem found in a semantic flow.

	Validation is deliberately strict. A dialplan that compiles with dangling
	outputs or unreachable nodes is harder to debug than one that is rejected
	before it reaches FreeSWITCH.
	"""
	try:
		graph = load_flow(flow)
	except FlowError as exc:
		return [str(exc)]

	errors: list[str] = []
	schema = graph.get("schema")
	if schema is not None and schema != SCHEMA_VERSION:
		errors.append(f"Unsupported flow schema {schema!r}; expected {SCHEMA_VERSION}.")
	nodes = graph.get("nodes")
	edges = graph.get("edges")
	if not isinstance(nodes, list) or not nodes:
		return errors + ["The flow must contain a non-empty nodes array."]
	if not isinstance(edges, list):
		return errors + ["The flow must contain an edges array."]

	by_id: dict[str, dict[str, Any]] = {}
	specs: dict[str, NodeSpec] = {}
	datas: dict[str, dict[str, Any]] = {}
	for index, node in enumerate(nodes):
		if not isinstance(node, dict):
			errors.append(f"nodes[{index}] is not an object.")
			continue
		node_id = str(node.get("id") or "").strip()
		if not node_id:
			errors.append(f"nodes[{index}] has no id.")
			continue
		if node_id in by_id:
			errors.append(f"Duplicate node id {node_id!r}.")
			continue
		node_type = str(node.get("type") or "").strip().lower()
		spec = NODE_SPECS.get(node_type)
		if not spec:
			errors.append(f"Node {node_id!r} has unknown type {node_type!r}.")
			continue
		data = node.get("data") or {}
		if not isinstance(data, dict):
			errors.append(f"Node {node_id!r} data must be an object.")
			data = {}
		by_id[node_id] = node
		specs[node_id] = spec
		datas[node_id] = data
		errors.extend(_validate_required(node_id, spec, data))
		if spec.validate_data:
			errors.extend(spec.validate_data(data))

	entry = str(graph.get("entry") or "").strip()
	if not entry:
		errors.append("The flow must name an entry node.")
	elif entry not in by_id:
		errors.append(f"The entry node {entry!r} does not exist.")

	targets: dict[str, dict[str, str]] = {node_id: {} for node_id in by_id}
	adjacency: dict[str, list[str]] = {node_id: [] for node_id in by_id}
	edge_ids: set[str] = set()
	for index, edge in enumerate(edges):
		if not isinstance(edge, dict):
			errors.append(f"edges[{index}] is not an object.")
			continue
		edge_id = str(edge.get("id") or "").strip()
		if edge_id:
			if edge_id in edge_ids:
				errors.append(f"Duplicate edge id {edge_id!r}.")
			edge_ids.add(edge_id)
		source = str(edge.get("source") or "").strip()
		target = str(edge.get("target") or "").strip()
		if source not in by_id:
			errors.append(f"edges[{index}] points from missing node {source!r}.")
			continue
		if target not in by_id:
			errors.append(f"edges[{index}] points at missing node {target!r}.")
			continue
		spec = specs[source]
		handle = str(edge.get("sourceHandle") or "next").strip() or "next"
		if spec.terminal:
			errors.append(f"Node {source!r} ({spec.type}) is terminal and cannot have an outgoing edge.")
			continue
		try:
			outputs = spec.output_handles(datas[source])
		except FlowError as exc:
			errors.append(f"Node {source!r}: {exc}")
			continue
		if handle not in outputs:
			errors.append(
				f"Node {source!r} ({spec.type}) has no output {handle!r}; "
				f"expected one of {', '.join(outputs) or 'none'}."
			)
			continue
		if handle in targets[source]:
			errors.append(f"Node {source!r} has more than one edge from output {handle!r}.")
			continue
		targets[source][handle] = target
		adjacency[source].append(target)

	if entry in by_id:
		reachable: set[str] = set()
		queue = [entry]
		while queue:
			node_id = queue.pop()
			if node_id in reachable:
				continue
			reachable.add(node_id)
			queue.extend(adjacency.get(node_id, []))
		for node_id in by_id:
			if node_id not in reachable:
				errors.append(f"Node {node_id!r} is not reachable from entry {entry!r}.")
		for node_id, spec in specs.items():
			if node_id not in reachable or spec.terminal:
				continue
			try:
				outputs = spec.output_handles(datas[node_id])
			except FlowError:
				continue
			for handle in outputs:
				if handle not in targets[node_id]:
					errors.append(
						f"Node {node_id!r} ({spec.type}) is missing an edge for output {handle!r}."
					)

	# Keep the first occurrence of each message for a readable UI list.
	return list(dict.fromkeys(errors))


def _slug(value: str) -> str:
	slug = re.sub(r"[^A-Za-z0-9]+", "_", value or "").strip("_").lower()
	return slug or "flow"


def _action_line(application: str, data: str | None = None, indent: int = 8) -> str:
	padding = " " * indent
	if data is None or str(data) == "":
		return f"{padding}<action application={quoteattr(application)}/>"
	return (
		f"{padding}<action application={quoteattr(application)} "
		f"data={quoteattr(str(data))}/>"
	)


def _extension_xml(name: str, expression: str, body: list[str]) -> str:
	lines = [
		f"    <extension name={quoteattr(name)}>",
		f"      <condition field=\"destination_number\" expression={quoteattr(expression)}>",
		*body,
		"      </condition>",
		"    </extension>",
	]
	return "\n".join(lines)


def _branch_suffix(handle: str) -> str:
	if handle.startswith("digit:"):
		return "digit_" + _slug(handle.split(":", 1)[1])
	return _slug(handle) or "branch"


def _reserve_name(base: str, used_names: set[str]) -> str:
	candidate = base
	counter = 2
	while candidate in used_names:
		candidate = f"{base}_{counter}"
		counter += 1
	used_names.add(candidate)
	return candidate


def _branch_extension_xml(
	name: str,
	dispatch_expression: str,
	field_name: str,
	expression: str,
	transfer_data: str,
) -> str:
	"""Emit one branch selector extension.

	FreeSWITCH evaluates peer conditions with AND semantics. Every selector
	re-checks the dispatch destination and then tests its own branch condition.
	Extensions are evaluated in document order, so a failed condition falls
	through to the next selector instead of stopping the flow.
	"""
	lines = [
		f"    <extension name={quoteattr(name)}>",
		f"      <condition field=\"destination_number\" expression={quoteattr(dispatch_expression)}/>",
		f"      <condition field={quoteattr(field_name)} expression={quoteattr(expression)}>",
		_action_line("transfer", transfer_data),
		"      </condition>",
		"    </extension>",
	]
	return "\n".join(lines)


def compile_flow(
	flow: Any,
	*,
	context: str | None = None,
	name: str | None = None,
	destination_number: str | None = None,
) -> str:
	"""Compile a semantic flow into one or more FreeSWITCH extensions.

	The entry extension matches ``destination_number`` and transfers to the
	entry node. Every node extension matches its own synthetic extension name;
	branch nodes transfer to a selector and each branch is a selector extension
	with the same dispatch destination plus its own condition. This keeps the
	XML flat enough to diff and test without nested-condition break semantics.
	"""
	graph = load_flow(flow)
	errors = validate_flow(graph)
	if errors:
		raise FlowError("Invalid flow:\n- " + "\n- ".join(errors))

	context_name = (context or graph.get("context") or "default").strip() or "default"
	flow_name = (
		name
		or graph.get("name")
		or graph.get("extension_name")
		or "flow"
	).strip() or "flow"
	pattern = (destination_number or graph.get("destination_number") or "").strip()
	if not pattern:
		raise FlowError("A destination_number pattern is required.")
	try:
		re.compile(pattern)
	except re.error as exc:
		raise FlowError(f"destination_number is not a valid regular expression: {exc}") from exc

	nodes: list[dict[str, Any]] = graph["nodes"]
	by_id = {str(node["id"]): node for node in nodes}
	prefix = _slug(flow_name)
	used_names = {f"fs_flow_{prefix}_entry"}
	extensions: dict[str, str] = {}
	for node in nodes:
		node_id = str(node["id"])
		extensions[node_id] = _reserve_name(f"fs_flow_{prefix}_{_slug(node_id)}", used_names)

	targets: dict[str, dict[str, str]] = {}
	for edge in graph["edges"]:
		source = str(edge["source"])
		handle = str(edge.get("sourceHandle") or "next").strip() or "next"
		targets.setdefault(source, {})[handle] = str(edge["target"])

	entry = str(graph["entry"])
	entry_extension = f"fs_flow_{prefix}_entry"
	blocks = [
		_extension_xml(
			entry_extension,
			pattern,
			[
				_action_line("set", f"fs_switch_flow={prefix}"),
				_action_line("transfer", f"{extensions[entry]} XML {context_name}"),
			],
		)
	]

	for node in nodes:
		node_id = str(node["id"])
		spec = NODE_SPECS[str(node["type"]).strip().lower()]
		data = node.get("data") or {}
		rendered = spec.render(data, context_name)
		body = [_action_line(application, payload) for application, payload in rendered.actions]
		base_extension = extensions[node_id]
		if rendered.branches:
			selector = _reserve_name(f"{base_extension}__select", used_names)
			body.append(_action_line("transfer", f"{selector} XML {context_name}"))
			blocks.append(
				_extension_xml(
					base_extension,
					"^" + re.escape(base_extension) + "$",
					body,
				)
			)
			dispatch_expression = "^" + re.escape(selector) + "$"
			for index, branch in enumerate(rendered.branches):
				target = targets.get(node_id, {}).get(branch.handle)
				if target is None:
					raise FlowError(
						f"Node {node_id!r} ({spec.type}) has no target for output {branch.handle!r}."
					)
				if index == 0:
					branch_name = selector
				else:
					branch_name = _reserve_name(
						f"{selector}_{_branch_suffix(branch.handle)}",
						used_names,
					)
				blocks.append(
					_branch_extension_xml(
						branch_name,
						dispatch_expression,
						branch.field,
						branch.expression,
						f"{extensions[target]} XML {context_name}",
					)
				)
		else:
			if not spec.terminal:
				target = targets.get(node_id, {}).get("next")
				if target is None:
					raise FlowError(f"Node {node_id!r} ({spec.type}) has no next target.")
				body.append(_action_line("transfer", f"{extensions[target]} XML {context_name}"))
			blocks.append(
				_extension_xml(
					base_extension,
					"^" + re.escape(base_extension) + "$",
					body,
				)
			)

	# by_id is intentionally retained as a simple assertion that the graph
	# contains exactly the nodes expected by the entry lookup.
	if entry not in by_id:
		raise FlowError(f"The entry node {entry!r} does not exist.")
	return "\n".join(blocks)
