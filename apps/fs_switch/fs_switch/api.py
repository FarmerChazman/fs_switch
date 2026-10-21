"""HTTP API for mod_xml_curl, the console and the browser softphone."""

from __future__ import annotations

import hmac
from types import SimpleNamespace
from xml.sax.saxutils import quoteattr

import frappe

from fs_switch.dialplan import DialplanError, compile_dialplan, compile_extension
from fs_switch.esl import live_data as read_live_data
from fs_switch.esl import run_action as execute_action

SETTINGS_DOCTYPE = "FS Switch Settings"
AGENT_STATUSES = ("Logged Out", "Available", "On Break")


def _settings():
	return frappe.get_single(SETTINGS_DOCTYPE)


def _check_secret():
	expected = _settings().get_password("xml_curl_secret", raise_exception=False) or ""
	given = frappe.form_dict.get("secret") or ""
	if not expected or not given or not hmac.compare_digest(given, expected):
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
		_xml_response(_directory_xml(frappe.form_dict.get("domain")))
	elif section == "dialplan":
		_xml_response(_dialplan_xml())
	elif section == "configuration" and frappe.form_dict.get("key_value") == "callcenter.conf":
		_xml_response(_callcenter_xml())
	else:
		_empty()


def _attr(value) -> str:
	return quoteattr(str(value if value is not None else ""))


def _directory_xml(domain: str | None) -> str:
	settings = _settings()
	users = []
	for row in frappe.get_all(
		"FS Extension",
		filters={"enabled": 1},
		fields=["name", "user", "display_name", "extension"],
		order_by="extension asc",
	):
		doc = frappe.get_doc("FS Extension", row.name)
		full_name = row.display_name
		if not full_name and row.user:
			full_name = frappe.db.get_value("User", row.user, "full_name")
		context = doc.context or settings.default_context or "default"
		users.append(
			f"<user id={_attr(doc.extension)}>"
			"<params>"
			f'<param name="password" value={_attr(doc.get_password("sip_password"))}/>'
			f'<param name="vm-password" value={_attr(doc.extension)}/>'
			"</params>"
			"<variables>"
			f'<variable name="user_context" value={_attr(context)}/>'
			f'<variable name="effective_caller_id_name" value={_attr(full_name or doc.extension)}/>'
			f'<variable name="effective_caller_id_number" value={_attr(doc.caller_id_number or doc.extension)}/>'
			"</variables></user>"
		)

	domain_name = domain or settings.sip_domain or "$${domain}"
	return (
		'<document type="freeswitch/xml">'
		f'<section name="directory"><domain name={_attr(domain_name)}>'
		"<params>"
		'<param name="dial-string" value="{^^:sip_invite_domain=${dialed_domain}:presence_id=${dialed_user}@${dialed_domain}}${sofia_contact(*/${dialed_user}@${dialed_domain})}"/>'
		"</params>"
		'<groups><group name="fs_switch"><users>' + "".join(users) + "</users></group></groups>"
		"</domain></section></document>"
	)


def _dialplan_xml() -> str:
	settings = _settings()
	plans = frappe.get_all(
		"FS Dialplan",
		filters={"enabled": 1},
		fields=["name", "title", "context", "extension_name", "destination_number", "priority", "graph", "enabled"],
		order_by="priority asc, modified asc",
	)
	valid = []
	for row in plans:
		plan = SimpleNamespace(
			name=row.name,
			title=row.title,
			context=row.context,
			extension_name=row.extension_name,
			destination_number=row.destination_number,
			priority=row.priority,
			graph=row.graph,
			enabled=row.enabled,
		)
		try:
			compile_extension(plan)
		except DialplanError as exc:
			frappe.log_error(title=f"FS Switch dialplan {row.name}", message=str(exc))
			continue
		valid.append(plan)
	return compile_dialplan(valid, settings)


def _callcenter_xml() -> str:
	settings = _settings()
	context = (settings.default_context or "default").strip() or "default"
	hold = settings.hold_music_file or "local_stream://moh"
	queues, tiers, agents = [], [], []
	used_extensions = set()

	for row in frappe.get_all(
		"FS Queue", filters={"enabled": 1}, fields=["name"], order_by="queue_name asc"
	):
		queue = frappe.get_doc("FS Queue", row.name)
		members = [(row.extension, row.level or 1, row.position or 0) for row in queue.agents or []]
		if queue.backup_queue:
			backup = frappe.get_doc("FS Queue", queue.backup_queue)
			members += [
				(row.extension, 2, row.position or 0)
				for row in backup.agents or []
				if row.extension not in {member[0] for member in members}
			]
		if not members:
			continue
		queue_name = f"{queue.queue_name}@{context}"
		queues.append(
			f"<queue name={_attr(queue_name)}>"
			f'<param name="strategy" value={_attr(queue.strategy or "longest-idle-agent")}/>'
			f'<param name="moh-sound" value={_attr(queue.music_on_hold or hold)}/>'
			f'<param name="max-wait-time" value={_attr(int(queue.max_wait_seconds or 180))}/>'
			'<param name="max-wait-time-with-no-agent" value="30"/>'
			'<param name="discard-abandoned-after" value="60"/>'
			'<param name="abandoned-resume-allowed" value="false"/>'
			'<param name="tier-rules-apply" value="false"/>'
			'<param name="tier-rule-no-agent-no-wait" value="true"/>'
			"</queue>"
		)
		for extension, level, position in members:
			tiers.append(
				f'<tier agent={_attr(f"{extension}@{context}")} '
				f'queue={_attr(queue_name)} level="{int(level)}" position="{int(position)}"/>'
			)
			used_extensions.add(extension)

	extension_rows = (
		frappe.get_all(
			"FS Extension",
			filters={"enabled": 1, "name": ["in", sorted(used_extensions)]},
			fields=["name", "extension", "agent_status"],
			order_by="extension asc",
		)
		if used_extensions
		else []
	)
	for row in extension_rows:
		status = row.agent_status if row.agent_status in AGENT_STATUSES else "Logged Out"
		agents.append(
			f'<agent name={_attr(f"{row.extension}@{context}")} type="callback" '
			f'contact={_attr(f"[leg_timeout=30]user/{row.extension}@$${{domain}}")} '
			f'status={_attr(status)} max-no-answer="0" wrap-up-time="30" '
			'reject-delay-time="10" busy-delay-time="0" no-answer-delay-time="10"/>'
		)

	return (
		'<document type="freeswitch/xml">'
		'<section name="configuration"><configuration name="callcenter.conf" description="Call center">'
		"<settings></settings>"
		"<queues>" + "".join(queues) + "</queues>"
		"<agents>" + "".join(agents) + "</agents>"
		"<tiers>" + "".join(tiers) + "</tiers>"
		"</configuration></section></document>"
	)


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
	return {
		"user": frappe.session.user,
		"full_name": frappe.utils.get_fullname(frappe.session.user),
		"roles": frappe.get_roles(),
		"is_admin": "System Manager" in frappe.get_roles(),
		"settings": {
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
			"extensions": frappe.db.count("FS Extension", {"enabled": 1}),
			"gateways": frappe.db.count("FS Gateway", {"enabled": 1}),
			"queues": frappe.db.count("FS Queue", {"enabled": 1}),
			"dialplans": frappe.db.count("FS Dialplan", {"enabled": 1}),
		},
		"version": "0.1.0",
	}


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


@frappe.whitelist()
def preview_dialplan(name: str | None = None, graph: str | None = None):
	_require_admin()
	if name:
		doc = frappe.get_doc("FS Dialplan", name)
		return {"xml": compile_extension(doc)}
	if graph:
		plan = SimpleNamespace(
			graph=graph,
			extension_name="preview",
			destination_number="^1000$",
			title="Preview",
			context="default",
			enabled=1,
		)
		return {"xml": compile_extension(plan)}
	frappe.throw("Pass a dialplan name or a graph.")


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
