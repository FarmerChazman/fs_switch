"""HTTP API for mod_xml_curl, the console and the browser softphone."""

from __future__ import annotations

import hmac
from types import SimpleNamespace

import frappe

from fs_switch.call_setup import (
	NOT_FOUND_DOCUMENT,
	expected_secret_hash,
	invalidate_dialplan,
	secret_hash,
	serve_callcenter,
	serve_dialplan,
	serve_directory,
)
from fs_switch.dialplan import compile_extension
from fs_switch.diff import diff_flow
from fs_switch.esl import ESLError
from fs_switch.esl import live_data as read_live_data
from fs_switch.esl import run_action as execute_action
from fs_switch.flow import SCHEMA_VERSION, FlowError, node_catalog, validate_flow
from fs_switch.publish import publish_flow, rollback_flow
from fs_switch.simulator import simulate_flow
from fs_switch.tenants import DEFAULT_TENANT

SETTINGS_DOCTYPE = "FS Switch Settings"


def _settings():
	return frappe.get_single(SETTINGS_DOCTYPE)


def _check_secret():
	try:
		expected = expected_secret_hash()
	except Exception:
		# Fail closed when neither Redis nor MariaDB can authenticate the call.
		frappe.throw("Forbidden", frappe.PermissionError)
	given = frappe.form_dict.get("secret") or ""
	if not expected or not given or not hmac.compare_digest(secret_hash(given), expected):
		frappe.throw("Forbidden", frappe.PermissionError)


def _xml_response(body: str):
	frappe.response["type"] = "download"
	frappe.response["filename"] = "freeswitch.xml"
	frappe.response["content_type"] = "text/xml"
	frappe.response["filecontent"] = '<?xml version="1.0" encoding="UTF-8"?>\n' + body


def _empty():
	_xml_response('<document type="freeswitch/xml"></document>')


@frappe.whitelist(allow_guest=True)
def xml_curl():
	"""Entry point for FreeSWITCH's mod_xml_curl bindings."""
	_check_secret()
	section = frappe.form_dict.get("section")
	if section == "directory":
		_xml_response(_serve(serve_directory, frappe.form_dict.get("domain")))
	elif section == "dialplan":
		_xml_response(_serve(serve_dialplan, frappe.form_dict.get("context")))
	elif section == "configuration" and frappe.form_dict.get("key_value") == "callcenter.conf":
		_xml_response(_serve(serve_callcenter, frappe.form_dict.get("context")))
	else:
		_empty()


def _serve(handler, *args) -> str:
	"""Never let a handler error escape the call-setup path."""
	try:
		return handler(*args)
	except Exception as exc:
		frappe.log_error(
			title="FS Switch xml-curl",
			message=f"{getattr(handler, '__name__', handler)} failed: {exc}",
		)
		return NOT_FOUND_DOCUMENT


def _require_admin():
	if frappe.session.user == "Guest":
		frappe.throw("Please log in.", frappe.PermissionError)
	if "System Manager" not in frappe.get_roles():
		frappe.throw("FS Switch is limited to System Managers.", frappe.PermissionError)


@frappe.whitelist()
def get_bootstrap():
	"""Small, secret-free payload for the console shell."""
	if frappe.session.user == "Guest":
		frappe.throw("Please log in.", frappe.PermissionError)
	settings = _settings()
	tenant = settings.default_tenant or DEFAULT_TENANT
	return {
		"user": frappe.session.user,
		"full_name": frappe.utils.get_fullname(frappe.session.user),
		"roles": frappe.get_roles(),
		"is_admin": "System Manager" in frappe.get_roles(),
		"settings": {
			"default_tenant": settings.default_tenant or DEFAULT_TENANT,
			"main_did": settings.main_did,
			"default_context": settings.default_context,
			"sip_domain": settings.sip_domain,
			"webrtc_url": settings.webrtc_url,
			"public_ip": settings.public_ip,
			"esl_host": settings.esl_host,
			"esl_port": settings.esl_port,
			"allow_internal_calls": settings.allow_internal_calls,
			"ivr_prompt_file": settings.ivr_prompt_file,
			"hold_music_file": settings.hold_music_file,
			"voicemail_path": settings.voicemail_path,
			"recording_path": settings.recording_path,
			"default_gateway": settings.default_gateway,
			"outbound_caller_id": settings.outbound_caller_id,
			"recording_enabled": settings.recording_enabled,
		},
		"counts": {
			"extensions": frappe.db.count(
				"FS Extension", {"enabled": 1, "tenant": tenant}
			),
			"gateways": frappe.db.count("FS Gateway", {"enabled": 1, "tenant": tenant}),
			"queues": frappe.db.count("FS Queue", {"enabled": 1, "tenant": tenant}),
			"dialplans": frappe.db.count("FS Dialplan", {"enabled": 1, "tenant": tenant}),
		},
		"version": "0.1.0",
	}


@frappe.whitelist()
def get_flow_catalog():
	"""Return the semantic node palette used by the flow editor.

	The catalog contains no secrets or tenant data, so authenticated read-only
	console users may view it even though they cannot save a flow.
	"""
	if frappe.session.user == "Guest":
		frappe.throw("Please log in.", frappe.PermissionError)
	return {"schema": SCHEMA_VERSION, "nodes": node_catalog()}


@frappe.whitelist(methods=["POST"])
def save_settings(
	main_did=None,
	default_context=None,
	sip_domain=None,
	webrtc_url=None,
	public_ip=None,
	esl_host=None,
	esl_port=None,
	xml_curl_secret=None,
	esl_password=None,
	allow_internal_calls=None,
	ivr_prompt_file=None,
	hold_music_file=None,
	voicemail_path=None,
	recording_path=None,
	default_gateway=None,
	outbound_caller_id=None,
	recording_enabled=None,
):
	"""Update the non-secret settings, and any secret that was explicitly supplied.

	Leaving a Password field blank in the console means "keep the current value";
	it must not overwrite a stored secret with an empty string.
	"""
	_require_admin()
	doc = _settings()
	values = {
		"main_did": main_did,
		"default_context": default_context,
		"sip_domain": sip_domain,
		"webrtc_url": webrtc_url,
		"public_ip": public_ip,
		"esl_host": esl_host,
		"ivr_prompt_file": ivr_prompt_file,
		"hold_music_file": hold_music_file,
		"voicemail_path": voicemail_path,
		"recording_path": recording_path,
		"default_gateway": default_gateway,
		"outbound_caller_id": outbound_caller_id,
	}
	for field, value in values.items():
		if value is not None:
			setattr(doc, field, value)
	if esl_port is not None and str(esl_port).strip() != "":
		doc.esl_port = int(esl_port)
	if allow_internal_calls is not None:
		doc.allow_internal_calls = 1 if allow_internal_calls else 0
	if recording_enabled is not None:
		doc.recording_enabled = 1 if recording_enabled else 0
	if xml_curl_secret:
		doc.xml_curl_secret = xml_curl_secret
	if esl_password:
		doc.esl_password = esl_password
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"ok": True}


@frappe.whitelist()
def get_live_data():
	_require_admin()
	return read_live_data()


@frappe.whitelist(methods=["POST"])
def run_live_action(action, uuid=None, destination=None, context=None, agent=None, status=None):
	_require_admin()
	try:
		reply = execute_action(
			action,
			uuid=uuid,
			destination=destination,
			context=context,
			agent=agent,
			status=status,
		)
	except (OSError, ValueError) as exc:
		frappe.throw(str(exc))
	return {"ok": True, "reply": reply}


@frappe.whitelist(methods=["POST"])
def validate_semantic_flow(graph: str | None = None):
	"""Validate an unsaved semantic flow for the visual editor.

	The editor calls this while the administrator edits so broken routes are
	visible before a save or publish. The response is intentionally a list of
	human-readable messages rather than a single exception.
	"""
	if frappe.session.user == "Guest":
		frappe.throw("Please log in.", frappe.PermissionError)
	if not graph:
		return {"valid": False, "errors": ["The flow is empty."]}
	try:
		errors = validate_flow(graph)
	except (FlowError, ValueError) as exc:
		errors = [str(exc)]
	return {"valid": not errors, "errors": errors}


@frappe.whitelist()
def preview_dialplan(
	name: str | None = None,
	graph: str | None = None,
	graph_format: str = "raw",
	extension_name: str | None = None,
	context: str | None = None,
	destination_number: str | None = None,
):
	_require_admin()
	if name:
		doc = frappe.get_doc("FS Dialplan", name)
		return {"xml": compile_extension(doc)}
	if graph:
		plan = SimpleNamespace(
			graph=graph,
			graph_format=graph_format or "raw",
			extension_name=(extension_name or "preview").strip() or "preview",
			destination_number=(destination_number or "^1000$").strip() or "^1000$",
			title="Preview",
			context=(context or "default").strip() or "default",
			enabled=1,
		)
		return {"xml": compile_extension(plan)}
	frappe.throw("Pass a dialplan name or a graph.")


@frappe.whitelist(methods=["POST"])
def simulate_route(
	graph: str | None = None,
	name: str | None = None,
	destination: str | None = None,
	at: str | None = None,
	digits: str | None = None,
	variables: str | None = None,
	destination_number: str | None = None,
	max_steps: int = 50,
):
	"""Walk a semantic Flow with call inputs and return the node path.

	The editor sends an unsaved graph so an administrator can test a route before
	saving or publishing. When ``name`` is supplied, the saved draft and its
	destination pattern are used instead.
	"""
	if frappe.session.user == "Guest":
		frappe.throw("Please log in.", frappe.PermissionError)
	pattern = (destination_number or "").strip()
	if name:
		doc = frappe.get_doc("FS Dialplan", name)
		if str(doc.graph_format or "raw").strip().lower() != "semantic":
			frappe.throw("The route simulator supports semantic Flows only.")
		graph = graph or doc.graph
		pattern = pattern or (doc.destination_number or "")
	if not graph:
		frappe.throw("Pass a Flow graph or a Flow name.")
	try:
		return simulate_flow(
			graph,
			destination=destination,
			at=at,
			digits=digits,
			variables=variables,
			destination_number=pattern,
			max_steps=max_steps,
		)
	except ValueError as exc:
		frappe.throw(str(exc))


def _flow_payload(doc) -> dict:
	payload = doc.as_dict()
	payload.pop("versions", None)
	return payload


def _reload_xml() -> dict:
	"""Ask FreeSWITCH to reload after a publish, without failing the publish."""
	try:
		return {"ok": True, "reply": execute_action("reload")}
	except (OSError, ESLError, ValueError) as exc:
		return {"ok": False, "error": str(exc)}


@frappe.whitelist(methods=["POST"])
def publish_dialplan(name: str, note: str | None = None):
	"""Compile the saved draft and make it the published Flow version."""
	_require_admin()
	doc = frappe.get_doc("FS Dialplan", name)
	try:
		version = publish_flow(doc, note=note, published_by=frappe.session.user)
	except ValueError as exc:
		frappe.throw(str(exc))
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	invalidate_dialplan()
	return {
		"version": version,
		"dialplan": _flow_payload(doc),
		"reload": _reload_xml(),
	}


@frappe.whitelist(methods=["POST"])
def rollback_dialplan(name: str, version: int):
	"""Serve an earlier published version without changing the draft."""
	_require_admin()
	doc = frappe.get_doc("FS Dialplan", name)
	try:
		target = rollback_flow(doc, version, published_by=frappe.session.user)
	except ValueError as exc:
		frappe.throw(str(exc))
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	invalidate_dialplan()
	return {
		"version": target,
		"dialplan": _flow_payload(doc),
		"reload": _reload_xml(),
	}


@frappe.whitelist()
def get_dialplan_versions(name: str):
	"""List published versions for the rollback drawer."""
	_require_admin()
	doc = frappe.get_doc("FS Dialplan", name)
	rows = sorted(
		doc.versions or [],
		key=lambda row: int(row.version or 0),
		reverse=True,
	)
	return {
		"name": doc.name,
		"title": doc.title,
		"published_version": doc.published_version,
		"versions": [
			{
				"version": row.version,
				"tenant": row.tenant,
				"published_on": row.published_on,
				"published_by": row.published_by,
				"graph_format": row.graph_format,
				"context": row.context,
				"priority": row.priority,
				"note": row.note,
			}
			for row in rows
		],
	}


@frappe.whitelist()
def get_dialplan_diff(name: str):
	"""Compare the saved Draft with the currently Published version."""
	if frappe.session.user == "Guest":
		frappe.throw("Please log in.", frappe.PermissionError)
	doc = frappe.get_doc("FS Dialplan", name)
	return diff_flow(doc)


@frappe.whitelist()
def get_softphone_config():
	"""Return the caller's own SIP credentials for a browser softphone.

	Only the owner of the extension receives the password, over the authenticated
	Frappe session. No list endpoint exposes SIP passwords.
	"""
	if frappe.session.user == "Guest":
		return {"enabled": 0}
	extension = frappe.db.get_value(
		"FS Extension", {"user": frappe.session.user, "enabled": 1}, "name"
	)
	if not extension:
		return {"enabled": 0}
	doc = frappe.get_doc("FS Extension", extension)
	settings = _settings()
	return {
		"enabled": 1,
		"ws_url": settings.webrtc_url or "",
		"domain": settings.sip_domain or "",
		"extension": doc.extension,
		"password": doc.get_password("sip_password", raise_exception=False) or "",
		"display_name": doc.display_name
		or frappe.utils.get_fullname(frappe.session.user)
		or doc.extension,
	}
