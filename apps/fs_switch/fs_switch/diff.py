"""Compare a Flow Draft with the currently Published version.

The diff is a read-only projection. It never compiles for serving, changes the
Draft or touches the call-setup cache. The semantic graph is compared by node
id and by connection identity, so moving a node on the canvas or renumbering an
edge id does not look like a routing change. The compiled XML diff catches
settings that are not stored in the published snapshot, such as the extension
name and destination pattern.
"""

from __future__ import annotations

import difflib
import json
from typing import Any

from fs_switch.dialplan import compile_extension
from fs_switch.flow import FlowError, NODE_SPECS, load_flow
from fs_switch.publish import published_status
from fs_switch.tenants import tenant_or_default

XML_DIFF_LIMIT = 2000


def diff_flow(doc) -> dict[str, Any]:
	"""Return a structured Draft-versus-Published diff for one Flow."""
	errors: list[str] = []
	never_published = not getattr(doc, "published_on", None)

	draft_graph = _parse_graph(getattr(doc, "graph", None), "Draft", errors)
	published_graph = _parse_graph(
		getattr(doc, "published_graph", None), "Published", errors
	)
	if not never_published and not published_graph:
		errors.append(
			"The Published version has no graph snapshot; only settings and XML "
			"can be compared."
		)

	nodes = _node_diff(published_graph, draft_graph)
	edges = _edge_diff(published_graph, draft_graph)
	entry = _entry_diff(published_graph, draft_graph)
	settings = _settings(doc, never_published)
	xml = _xml_diff(doc, never_published, errors)

	settings_changed = any(item["changed"] for item in settings)
	graph_changed = (
		entry["changed"]
		or bool(nodes["added"])
		or bool(nodes["removed"])
		or bool(nodes["changed"])
		or bool(edges["added"])
		or bool(edges["removed"])
	)
	has_changes = (
		never_published
		or graph_changed
		or settings_changed
		or xml["changed"]
		or bool(errors)
	)

	return {
		"name": getattr(doc, "name", ""),
		"title": getattr(doc, "title", ""),
		"graph_format": _format(getattr(doc, "graph_format", None)),
		"status": published_status(doc),
		"published_version": getattr(doc, "published_version", 0),
		"published_on": getattr(doc, "published_on", None),
		"published_by": getattr(doc, "published_by", ""),
		"never_published": never_published,
		"graph_available": bool(draft_graph) and bool(published_graph),
		"has_changes": has_changes,
		"entry": entry,
		"settings": settings,
		"settings_note": (
			"Extension name and destination pattern are not stored in the published "
			"snapshot; changes to them appear in the XML diff."
		),
		"nodes": nodes,
		"edges": edges,
		"xml": xml,
		"errors": errors,
		"summary": {
			"nodes_added": len(nodes["added"]),
			"nodes_removed": len(nodes["removed"]),
			"nodes_changed": len(nodes["changed"]),
			"edges_added": len(edges["added"]),
			"edges_removed": len(edges["removed"]),
			"settings_changed": sum(1 for item in settings if item["changed"]),
		},
	}


def _parse_graph(value, label: str, errors: list[str]):
	if not value:
		if label == "Draft":
			errors.append("The Draft graph is empty.")
		return None
	try:
		return load_flow(value)
	except FlowError as exc:
		errors.append(f"{label}: {exc}")
		return None


def _node_diff(published_graph, draft_graph) -> dict[str, list[dict]]:
	if not published_graph and not draft_graph:
		return {"added": [], "removed": [], "changed": []}
	published = _nodes(published_graph)
	draft = _nodes(draft_graph)

	added = [
		_node_info(draft[node_id])
		for node_id in draft
		if node_id not in published
	]
	removed = [
		_node_info(published[node_id])
		for node_id in published
		if node_id not in draft
	]
	changed = []
	for node_id in draft:
		if node_id not in published:
			continue
		changes = _node_changes(published[node_id], draft[node_id])
		if changes:
			changed.append(
				{
					**_node_info(draft[node_id]),
					"changes": changes,
				}
			)
	return {"added": added, "removed": removed, "changed": changed}


def _edge_diff(published_graph, draft_graph) -> dict[str, list[dict]]:
	if not published_graph and not draft_graph:
		return {"added": [], "removed": []}
	published = _edges(published_graph)
	draft = _edges(draft_graph)
	published_labels = _labels(published_graph)
	draft_labels = _labels(draft_graph)

	added = [
		_edge_info(draft[key], draft_labels)
		for key in draft
		if key not in published
	]
	removed = [
		_edge_info(published[key], published_labels)
		for key in published
		if key not in draft
	]
	return {"added": added, "removed": removed}


def _entry_diff(published_graph, draft_graph) -> dict[str, Any]:
	draft = _text((draft_graph or {}).get("entry"))
	published = _text((published_graph or {}).get("entry"))
	return {
		"draft": draft,
		"published": published,
		"changed": draft != published,
	}


def _settings(doc, never_published: bool) -> list[dict[str, Any]]:
	draft_tenant = tenant_or_default(getattr(doc, "tenant", None))
	published_tenant = (
		tenant_or_default(getattr(doc, "published_tenant", None))
		if not never_published
		else ""
	)
	draft_context = _context(getattr(doc, "context", None))
	published_context = (
		_context(getattr(doc, "published_context", None))
		if not never_published
		else ""
	)
	draft_priority = _priority(getattr(doc, "priority", 0))
	published_priority = _priority(getattr(doc, "published_priority", 0))
	draft_format = _format(getattr(doc, "graph_format", None))
	published_format = (
		_format(getattr(doc, "published_graph_format", None))
		if not never_published
		else ""
	)
	return [
		_setting("tenant", draft_tenant, published_tenant),
		_setting("context", draft_context, published_context),
		_setting("priority", draft_priority, published_priority),
		_setting("graph_format", draft_format, published_format),
	]


def _setting(field: str, draft, published) -> dict[str, Any]:
	return {
		"field": field,
		"draft": _safe(draft),
		"published": _safe(published),
		"changed": _canonical(draft) != _canonical(published),
	}


def _xml_diff(doc, never_published: bool, errors: list[str]) -> dict[str, Any]:
	published_xml = _text(getattr(doc, "published_xml", None))
	draft_xml = _text(getattr(doc, "compiled_xml", None))
	try:
		draft_xml = _text(compile_extension(doc))
	except Exception as exc:  # noqa: BLE001 - the diff must survive a broken draft
		errors.append(f"The Draft does not compile: {exc}")

	changed = draft_xml != published_xml
	diff_text = ""
	truncated = False
	note = ""
	if never_published:
		note = "This Flow has not been published yet."
	elif changed and not published_xml:
		note = "The Published version has no XML to compare."
	elif changed:
		lines = list(
			difflib.unified_diff(
				published_xml.splitlines(),
				draft_xml.splitlines(),
				fromfile="Published",
				tofile="Draft",
				lineterm="",
			)
		)
		truncated = len(lines) > XML_DIFF_LIMIT
		diff_text = "\n".join(lines[:XML_DIFF_LIMIT])
	return {
		"changed": changed,
		"diff": diff_text,
		"truncated": truncated,
		"note": note,
	}


def _nodes(graph) -> dict[str, dict]:
	if not graph:
		return {}
	return {
		str(node.get("id")): node
		for node in graph.get("nodes") or []
		if isinstance(node, dict) and _text(node.get("id"))
	}


def _edges(graph) -> dict[tuple[str, str, str], dict]:
	if not graph:
		return {}
	result = {}
	for edge in graph.get("edges") or []:
		if not isinstance(edge, dict):
			continue
		key = _edge_key(edge)
		if key[0] and key[2]:
			result[key] = edge
	return result


def _edge_key(edge) -> tuple[str, str, str]:
	return (
		_text(edge.get("source")),
		_text(edge.get("sourceHandle")) or "next",
		_text(edge.get("target")),
	)


def _labels(graph) -> dict[str, str]:
	if not graph:
		return {}
	return {
		node_id: _node_label(node)
		for node_id, node in _nodes(graph).items()
	}


def _node_info(node) -> dict[str, Any]:
	return {
		"id": _text(node.get("id")),
		"type": _text(node.get("type")).lower(),
		"label": _node_label(node),
	}


def _node_label(node) -> str:
	data = _data(node)
	label = _text(data.get("label"))
	if label:
		return label
	node_type = _text(node.get("type")).lower()
	spec = NODE_SPECS.get(node_type)
	if spec:
		return spec.label
	return _text(data.get("application")) or node_type or _text(node.get("id"))


def _node_changes(published, draft) -> list[dict[str, Any]]:
	changes = []
	published_type = _text(published.get("type")).lower()
	draft_type = _text(draft.get("type")).lower()
	if published_type != draft_type:
		changes.append(
			{
				"field": "type",
				"draft": _safe(draft_type),
				"published": _safe(published_type),
			}
		)
	published_data = _data(published)
	draft_data = _data(draft)
	for field in sorted(set(published_data) | set(draft_data)):
		if _canonical(published_data.get(field)) != _canonical(draft_data.get(field)):
			changes.append(
				{
					"field": field,
					"draft": _safe(draft_data.get(field)),
					"published": _safe(published_data.get(field)),
				}
			)
	return changes


def _edge_info(edge, labels) -> dict[str, Any]:
	source, handle, target = _edge_key(edge)
	return {
		"source": source,
		"source_handle": handle,
		"target": target,
		"source_label": labels.get(source, source),
		"target_label": labels.get(target, target),
	}


def _data(node) -> dict:
	data = node.get("data") if isinstance(node, dict) else None
	return data if isinstance(data, dict) else {}


def _text(value) -> str:
	return str(value or "").strip()


def _context(value) -> str:
	return _text(value) or "default"


def _format(value) -> str:
	return _text(value).lower() or "raw"


def _priority(value) -> int:
	try:
		return int(value or 0)
	except (TypeError, ValueError):
		return 0


def _canonical(value) -> str:
	return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _safe(value):
	try:
		return json.loads(json.dumps(value, default=str))
	except (TypeError, ValueError):
		return str(value)
