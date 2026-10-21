"""Compile FS Dialplan graph JSON into FreeSWITCH dialplan XML.

The graph model is deliberately small: nodes are FreeSWITCH applications and
edges define their order. This keeps the visual editor honest: what you see is
what the compiler emits. Branching conditions can be added later without
changing the stored document shape.
"""

from __future__ import annotations

import json
import re
from xml.sax.saxutils import quoteattr


class DialplanError(ValueError):
	"""Raised when a graph cannot be compiled."""


def load_graph(graph) -> tuple[list[dict], list[dict]]:
	if not graph:
		raise DialplanError("The dialplan graph is empty.")
	if isinstance(graph, str):
		try:
			graph = json.loads(graph)
		except ValueError as exc:
			raise DialplanError(f"The graph is not valid JSON: {exc}") from exc
	if not isinstance(graph, dict):
		raise DialplanError("The graph must be a JSON object.")

	nodes = graph.get("nodes") or []
	edges = graph.get("edges") or []
	if not isinstance(nodes, list) or not isinstance(edges, list):
		raise DialplanError("The graph must contain nodes and edges arrays.")
	if not nodes:
		raise DialplanError("The graph has no nodes.")
	return nodes, edges


def ordered_nodes(nodes: list[dict], edges: list[dict]) -> list[dict]:
	"""Return nodes in execution order, following the edges.

	Nodes without edges keep their array order. A cycle is an error rather than
	a silent fallback: call flows must be deterministic.
	"""
	index = {str(node.get("id")): i for i, node in enumerate(nodes)}
	by_id = {str(node.get("id")): node for node in nodes}
	indegree = {node_id: 0 for node_id in by_id}
	children: dict[str, list[str]] = {node_id: [] for node_id in by_id}

	for edge in edges:
		source = str(edge.get("source") or "")
		target = str(edge.get("target") or "")
		if source not in by_id or target not in by_id:
			raise DialplanError(f"An edge points at a missing node: {source!r} -> {target!r}.")
		children[source].append(target)
		indegree[target] += 1

	ready = sorted((node_id for node_id, degree in indegree.items() if degree == 0), key=index.get)
	result = []
	while ready:
		node_id = ready.pop(0)
		result.append(by_id[node_id])
		for child in children[node_id]:
			indegree[child] -= 1
			if indegree[child] == 0:
				ready.append(child)
		ready.sort(key=index.get)

	if len(result) != len(nodes):
		raise DialplanError("The graph contains a cycle. Remove the loop before saving.")
	return result


def _action(node: dict) -> str:
	data = node.get("data") or {}
	application = str(data.get("application") or "").strip()
	if not application:
		label = data.get("label") or node.get("id")
		raise DialplanError(f"Node {label!r} has no FreeSWITCH application.")
	data_value = data.get("data")
	if data_value is None or str(data_value) == "":
		return f"<action application={quoteattr(application)}/>"
	return f"<action application={quoteattr(application)} data={quoteattr(str(data_value))}/>"


def compile_extension(plan) -> str:
	"""Compile one FS Dialplan document-like object into an extension block."""
	nodes, edges = load_graph(plan.graph)
	extension_name = str(plan.extension_name or "").strip()
	destination = str(plan.destination_number or ".*").strip()
	if not extension_name:
		raise DialplanError("An extension name is required.")
	if not destination:
		raise DialplanError("A destination pattern is required.")
	# A bad regex should fail here, not inside FreeSWITCH.
	try:
		re.compile(destination)
	except re.error as exc:
		raise DialplanError(f"Destination pattern is not a valid regular expression: {exc}") from exc

	actions = "\n".join("      " + _action(node) for node in ordered_nodes(nodes, edges))
	return (
		f'    <extension name={quoteattr(extension_name)}>\n'
		f'      <condition field="destination_number" expression={quoteattr(destination)}>\n'
		f"{actions}\n"
		"      </condition>\n"
		"    </extension>"
	)


def inbound_pattern(did: str) -> str:
	"""Accept a DID with or without a leading plus, as carriers vary."""
	digits = re.sub(r"[^0-9]", "", did or "")
	if not digits:
		return ""
	return r"^\+?" + digits + r"$"


def compile_dialplan(plans: list, settings) -> str:
	"""Build the whole <document> for mod_xml_curl's dialplan binding.

	plans are FS Dialplan documents; settings is FS Switch Settings.
	"""
	context = (getattr(settings, "default_context", None) or "default").strip() or "default"
	enabled = [plan for plan in plans if getattr(plan, "enabled", 0)]
	enabled.sort(key=lambda plan: (int(getattr(plan, "priority", 0) or 0), plan.title or ""))

	# One context element per name. FreeSWITCH does not merge duplicate context
	# elements reliably, so every extension for a context is collected here.
	contexts: dict[str, list[str]] = {}
	for plan in enabled:
		plan_context = (getattr(plan, "context", None) or context).strip() or context
		contexts.setdefault(plan_context, []).append(compile_extension(plan))

	if getattr(settings, "allow_internal_calls", 1):
		contexts.setdefault(context, []).append(
			'    <extension name="fs_switch_internal">\n'
			'      <condition field="destination_number" expression="^(\\d{3,6})$">\n'
			'        <action application="bridge" data="user/$1@${domain_name}"/>\n'
			"      </condition>\n"
			"    </extension>"
		)

	# Inbound calls from a gateway land in the public context. Forward the main
	# DID into the default context so the configured dialplan can handle it.
	pattern = inbound_pattern(getattr(settings, "main_did", "") or "")
	if pattern:
		did = (getattr(settings, "main_did", "") or "").strip()
		contexts.setdefault("public", []).append(
			'    <extension name="fs_switch_inbound">\n'
			f'      <condition field="destination_number" expression={quoteattr(pattern)}>\n'
			f'        <action application="transfer" data={quoteattr(f"{did} XML {context}")}/>\n'
			"      </condition>\n"
			"    </extension>"
		)

	if not contexts:
		return '<document type="freeswitch/xml"></document>'

	# Put the default context first for readability; the rest keep insertion order.
	ordered = sorted(contexts, key=lambda name: (name != context, name))
	blocks = [
		f'  <context name={quoteattr(name)}>\n' + "\n".join(contexts[name]) + "\n  </context>"
		for name in ordered
	]
	return (
		'<document type="freeswitch/xml">\n'
		'<section name="dialplan">\n'
		+ "\n".join(blocks)
		+ "\n</section>\n</document>"
	)
