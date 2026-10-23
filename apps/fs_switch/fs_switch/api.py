"""HTTP API for mod_xml_curl, the console and the browser softphone."""

from __future__ import annotations

import hmac
from types import SimpleNamespace
from urllib.parse import urlparse

import frappe

from fs_switch.call_setup import (
	NOT_FOUND_DOCUMENT,
	expected_secret_hash,
	invalidate_dialplan,
	resolve_tenant,
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
from fs_switch.permissions import (
	require_supervisor,
	require_system_manager,
	require_tenant_read,
	require_tenant_write,
)
from fs_switch.publish import publish_flow, rollback_flow
from fs_switch.simulator import simulate_flow
from fs_switch.tenants import (
	DEFAULT_TENANT,
	accessible_tenants,
	can_supervise_tenant,
	can_write_tenant,
	is_system_manager,
	role_for_tenant,
	tenant_or_default,
)

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


def _require_authenticated():
	if frappe.session.user == "Guest":
		frappe.throw("Please log in.", frappe.PermissionError)


def _require_admin():
	"""Backward-compatible name for a System Manager-only action."""
	require_system_manager("FS Switch settings are limited to System Managers.")


def _require_config_access():
	"""Require at least one Tenant role that can read configuration."""
	_require_authenticated()
	if is_system_manager():
		return
	if any(row["role"] in ("Admin", "Supervisor") for row in accessible_tenants()):
		return
	frappe.throw("You need an Admin or Supervisor role to view configuration.", frappe.PermissionError)


def _socketio_url() -> str:
	"""Return the browser-facing Socket.IO origin.

	In a bench the socket server usually runs on ``socketio_port`` (9000) while
	the web server runs on 8000. A reverse proxy can expose both on one origin,
	in which case ``fs_switch_socketio_url`` can be set in site_config.
	"""
	configured = frappe.conf.get("fs_switch_socketio_url")
	if configured:
		return str(configured).rstrip("/")
	port = frappe.conf.get("socketio_port")
	base = frappe.utils.get_url()
	if port and str(port) not in ("0", ""):
		parsed = urlparse(base)
		host = parsed.hostname or "localhost"
		if ":" in host and not host.startswith("["):
			host = f"[{host}]"
		return f"{parsed.scheme}://{host}:{int(port)}"
	return base.rstrip("/")


def _active_tenant(requested=None):
	"""Pick the requested Tenant if the caller may read it, else the first one."""
	tenants = accessible_tenants()
	names = {row["tenant"] for row in tenants}
	if requested:
		requested = tenant_or_default(requested)
		if requested not in names:
			frappe.throw("You do not have access to this Tenant.", frappe.PermissionError)
		return requested
	configured = tenant_or_default(
		frappe.db.get_single_value(SETTINGS_DOCTYPE, "default_tenant")
	)
	if configured in names:
		return configured
	return next(iter(sorted(names)), None)


def _live_context(value) -> str:
	text = str(value or "").strip()
	if "@" in text:
		return text.rsplit("@", 1)[1]
	return text


def _annotate_live(data):
	"""Add Tenant labels to live rows so the console can filter and route them."""
	if not isinstance(data, dict):
		return data
	for channel in data.get("channels") or []:
		channel["tenant"] = resolve_tenant(context=channel.get("context"))
	for agent in data.get("agents") or []:
		context = _live_context(
			agent.get("queue") or agent.get("agent") or agent.get("name") or ""
		)
		agent["tenant"] = resolve_tenant(context=context) if context else resolve_tenant()
	for queue in data.get("queues") or []:
		context = _live_context(queue.get("name") or "")
		queue["tenant"] = resolve_tenant(context=context) if context else resolve_tenant()
	for registration in data.get("registrations") or []:
		registration["tenant"] = resolve_tenant(domain=registration.get("realm"))
	return data


def _filter_live(data, tenant=None):
	"""Filter an annotated live snapshot to one Tenant or the caller's Tenants."""
	tenant = tenant_or_default(tenant) if tenant else None
	allowed = {
		row["tenant"]
		for row in accessible_tenants()
		if row["role"] in ("System Manager", "Admin", "Supervisor")
	}
	if is_system_manager() and not tenant:
		return data
	allowed = allowed if tenant is None else {tenant}

	def keep(rows):
		return [row for row in rows or [] if row.get("tenant") in allowed]

	return {
		**(data or {}),
		"channels": keep((data or {}).get("channels")),
		"agents": keep((data or {}).get("agents")),
		"queues": keep((data or {}).get("queues")),
		"registrations": keep((data or {}).get("registrations")),
	}


def _assert_live_target_tenant(tenant, uuid=None, agent=None):
	"""Best-effort Tenant check for a live action.

	The channel or agent must already be visible in the caller's Tenant. A
	target that is not present is left to FreeSWITCH to reject; the point is to
	stop a supervisor in one Tenant from acting on another Tenant's live rows.
	"""
	if not tenant or is_system_manager():
		return
	if uuid:
		data = read_live_data()
		row = next(
			(channel for channel in data.get("channels") or [] if channel.get("uuid") == uuid),
			None,
		)
		if row and resolve_tenant(context=row.get("context")) != tenant:
			frappe.throw("That channel belongs to another Tenant.", frappe.PermissionError)
	if agent:
		context = _live_context(agent)
		if context and resolve_tenant(context=context) != tenant:
			frappe.throw("That agent belongs to another Tenant.", frappe.PermissionError)


@frappe.whitelist()
def get_bootstrap(tenant: str | None = None):
	"""Small, secret-free payload for the console shell."""
	_require_authenticated()
	settings = _settings()
	tenants = accessible_tenants()
	active = _active_tenant(tenant)
	role = role_for_tenant(frappe.session.user, active) if active else None
	can_write = bool(active and can_write_tenant(frappe.session.user, active))
	can_supervise = bool(active and can_supervise_tenant(frappe.session.user, active))
	counts = {"extensions": 0, "gateways": 0, "queues": 0, "dialplans": 0}
	if active and role in ("System Manager", "Admin", "Supervisor"):
		counts = {
			"extensions": frappe.db.count(
				"FS Extension", {"enabled": 1, "tenant": active}
			),
			"gateways": frappe.db.count("FS Gateway", {"enabled": 1, "tenant": active}),
			"queues": frappe.db.count("FS Queue", {"enabled": 1, "tenant": active}),
			"dialplans": frappe.db.count("FS Dialplan", {"enabled": 1, "tenant": active}),
		}
	elif active and role == "Agent":
		counts["extensions"] = frappe.db.count(
			"FS Extension",
			{"enabled": 1, "tenant": active, "user": frappe.session.user},
		)
	settings_payload = {}
	if role in ("System Manager", "Admin", "Supervisor"):
		settings_payload = {
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
		}
	return {
		"user": frappe.session.user,
		"full_name": frappe.utils.get_fullname(frappe.session.user),
		"roles": frappe.get_roles(),
		"is_admin": is_system_manager(),
		"can_manage_tenants": is_system_manager(),
		"can_write": can_write,
		"can_supervise": can_supervise,
		"active_tenant": active,
		"active_role": role,
		"tenants": tenants,
		"settings": settings_payload,
		"realtime": {
			"url": _socketio_url(),
			"site": frappe.local.site,
		},
		"counts": counts,
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
def get_live_data(tenant: str | None = None):
	tenant = (tenant or "").strip() or None
	require_supervisor(tenant)
	return _filter_live(_annotate_live(read_live_data()), tenant)


@frappe.whitelist(methods=["POST"])
def set_my_agent_status(status: str, tenant: str | None = None):
	"""Let an extension owner change their own call-center status."""
	_require_authenticated()
	status = str(status or "").strip()
	if status not in ("Logged Out", "Available", "On Break"):
		frappe.throw("Unsupported agent status.", frappe.ValidationError)
	tenant = (tenant or "").strip() or None
	filters = {"user": frappe.session.user, "enabled": 1}
	if tenant:
		filters["tenant"] = tenant_or_default(tenant)
	name = frappe.db.get_value("FS Extension", filters, "name")
	if not name:
		frappe.throw("No extension is assigned to your account for this Tenant.", frappe.PermissionError)
	doc = frappe.get_doc("FS Extension", name)
	if doc.user != frappe.session.user:
		frappe.throw("You can only change your own agent status.", frappe.PermissionError)
	doc.agent_status = status
	doc.save(ignore_permissions=True)
	context = (
		doc.context
		or frappe.db.get_value("FS Tenant", doc.tenant, "default_context")
		or _settings().default_context
		or "default"
	)
	try:
		reply = execute_action(
			"agent_status",
			agent=f"{doc.extension}@{context}",
			status=status,
		)
	except (OSError, ESLError, ValueError) as exc:
		return {"ok": True, "esl_ok": False, "error": str(exc)}
	return {"ok": True, "esl_ok": True, "reply": reply}


@frappe.whitelist(methods=["POST"])
def run_live_action(
	action,
	uuid=None,
	destination=None,
	context=None,
	agent=None,
	status=None,
	tenant=None,
):
	tenant = (tenant or "").strip() or None
	if action == "reload":
		require_system_manager("Only a System Manager can reload FreeSWITCH.")
	require_supervisor(tenant)
	if not tenant and not is_system_manager():
		frappe.throw("Select a Tenant before running a live action.", frappe.PermissionError)
	_assert_live_target_tenant(tenant, uuid=uuid, agent=agent)
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
	_require_config_access()
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
	_require_config_access()
	if name:
		doc = frappe.get_doc("FS Dialplan", name)
		require_tenant_read(doc.tenant)
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
	_require_config_access()
	pattern = (destination_number or "").strip()
	if name:
		doc = frappe.get_doc("FS Dialplan", name)
		require_tenant_read(doc.tenant)
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
	_require_authenticated()
	doc = frappe.get_doc("FS Dialplan", name)
	require_tenant_write(doc.tenant)
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
	_require_authenticated()
	doc = frappe.get_doc("FS Dialplan", name)
	require_tenant_write(doc.tenant)
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
	_require_authenticated()
	doc = frappe.get_doc("FS Dialplan", name)
	require_tenant_read(doc.tenant)
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
	_require_authenticated()
	doc = frappe.get_doc("FS Dialplan", name)
	require_tenant_read(doc.tenant)
	return diff_flow(doc)


@frappe.whitelist()
def get_softphone_config(tenant: str | None = None):
	"""Return the caller's own SIP credentials for a browser softphone.

	Only the owner of the extension receives the password, over the authenticated
	Frappe session. No list endpoint exposes SIP passwords.
	"""
	if frappe.session.user == "Guest":
		return {"enabled": 0}
	filters = {"user": frappe.session.user, "enabled": 1}
	if tenant:
		filters["tenant"] = tenant_or_default(tenant)
	extension = frappe.db.get_value("FS Extension", filters, "name")
	if not extension:
		return {"enabled": 0, "tenant": tenant_or_default(tenant) if tenant else None}
	doc = frappe.get_doc("FS Extension", extension)
	settings = _settings()
	tenant_context = frappe.db.get_value("FS Tenant", doc.tenant, "default_context")
	domain = frappe.db.get_value("FS Tenant", doc.tenant, "sip_domain") or settings.sip_domain or ""
	return {
		"enabled": 1,
		"tenant": doc.tenant,
		"context": doc.context or tenant_context or settings.default_context or "default",
		"ws_url": settings.webrtc_url or "",
		"domain": domain,
		"extension": doc.extension,
		"password": doc.get_password("sip_password", raise_exception=False) or "",
		"agent_status": doc.agent_status or "Logged Out",
		"display_name": doc.display_name
		or frappe.utils.get_fullname(frappe.session.user)
		or doc.extension,
	}
