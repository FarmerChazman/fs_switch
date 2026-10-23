"""Publish and rollback Flow versions.

A Flow keeps an editable draft plus the published XML FreeSWITCH may be served.
Publishing compiles the draft, stores an immutable version row and updates the
published pointer. Rolling back moves the published pointer to an earlier row;
the draft is left untouched so in-progress edits are not lost.
"""

from __future__ import annotations

from fs_switch.dialplan import compile_extension
from fs_switch.tenants import tenant_or_default


def _now():
	# Imported lazily so the publish rules can be unit-tested without a Frappe site.
	from frappe.utils import now_datetime

	return now_datetime()


def _text(value) -> str:
	return str(value or "").strip()


def _context(value) -> str:
	return _text(value) or "default"


def _priority(value) -> int:
	try:
		return int(value or 0)
	except (TypeError, ValueError):
		return 0


def _tenant(value) -> str:
	return tenant_or_default(value)


def _allow_publish(doc) -> None:
	flags = getattr(doc, "flags", None)
	if flags is not None:
		flags.publishing = True


def next_version(doc) -> int:
	versions = getattr(doc, "versions", None) or []
	return max((_priority(getattr(row, "version", 0)) for row in versions), default=0) + 1


def published_status(doc) -> str:
	"""Return Published only when the saved Draft matches the served version."""
	if not getattr(doc, "published_on", None):
		return "Draft"
	same_xml = (getattr(doc, "compiled_xml", "") or "") == (
		getattr(doc, "published_xml", "") or ""
	)
	same_context = _context(getattr(doc, "context", None)) == _context(
		getattr(doc, "published_context", None)
	)
	same_priority = _priority(getattr(doc, "priority", 0)) == _priority(
		getattr(doc, "published_priority", 0)
	)
	same_tenant = _tenant(getattr(doc, "tenant", None)) == _tenant(
		getattr(doc, "published_tenant", None)
	)
	return "Published" if same_xml and same_context and same_priority and same_tenant else "Draft"


def publish_flow(doc, note=None, published_by=None, timestamp=None) -> int:
	"""Compile the current draft and add a published version row.

	The caller owns the transaction and must save the document.
	"""
	xml = compile_extension(doc)
	_allow_publish(doc)
	version = next_version(doc)
	timestamp = timestamp or _now()
	user = published_by or getattr(doc, "modified_by", None) or "Administrator"
	context = _context(getattr(doc, "context", None))
	priority = _priority(getattr(doc, "priority", 0))
	graph_format = _text(getattr(doc, "graph_format", None)) or "raw"
	tenant = _tenant(getattr(doc, "tenant", None))

	doc.append(
		"versions",
		{
			"version": version,
			"tenant": tenant,
			"published_on": timestamp,
			"published_by": user,
			"graph": getattr(doc, "graph", "") or "",
			"graph_format": graph_format,
			"compiled_xml": xml,
			"context": context,
			"priority": priority,
			"note": _text(note),
		},
	)

	doc.compiled_xml = xml
	doc.published_version = version
	doc.published_on = timestamp
	doc.published_by = user
	doc.published_xml = xml
	doc.published_graph = getattr(doc, "graph", "") or ""
	doc.published_graph_format = graph_format
	doc.published_context = context
	doc.published_tenant = tenant
	doc.published_priority = priority
	return version


def rollback_flow(doc, version, published_by=None, timestamp=None) -> int:
	"""Point the published version at an existing version row.

	The draft stays as-is. If the draft differs, validation marks the Flow as
	Draft until it is published again.
	"""
	try:
		target_version = int(version)
	except (TypeError, ValueError) as exc:
		raise ValueError("A numeric published version is required.") from exc

	target = next(
		(
			row
			for row in (getattr(doc, "versions", None) or [])
			if _priority(getattr(row, "version", 0)) == target_version
		),
		None,
	)
	if target is None:
		raise ValueError(f"Published version {target_version} was not found.")
	xml = _text(getattr(target, "compiled_xml", None))
	if not xml:
		raise ValueError(f"Published version {target_version} has no XML.")

	_allow_publish(doc)
	doc.published_version = target_version
	doc.published_on = timestamp or _now()
	doc.published_by = published_by or getattr(doc, "modified_by", None) or "Administrator"
	doc.published_xml = getattr(target, "compiled_xml", "") or ""
	doc.published_graph = getattr(target, "graph", "") or ""
	doc.published_graph_format = _text(getattr(target, "graph_format", None)) or "raw"
	doc.published_context = _context(getattr(target, "context", None))
	doc.published_tenant = _tenant(
		getattr(target, "tenant", None) or getattr(doc, "tenant", None)
	)
	doc.published_priority = _priority(getattr(target, "priority", 0))
	return target_version
