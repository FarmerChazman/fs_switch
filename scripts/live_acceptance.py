"""Run inside a Frappe bench console: bench --site <site> console < live_acceptance.py.

Creates a small, idempotent acceptance fixture for Tenant roles, permissions,
DIDs, publishing and the call-setup handlers. It does not replace browser
Socket.IO or FreeSWITCH call testing.
"""

import json

import frappe

from fs_switch.call_setup import (
	expected_secret_hash,
	invalidate_all,
	serve_callcenter,
	serve_dialplan,
	serve_directory,
)
from fs_switch.dids import did_key, normalize_did
from fs_switch.esl_listener import _live_users
from fs_switch.publish import publish_flow
from fs_switch.tenants import (
	ensure_default_tenant,
	ensure_tenant_roles,
	sync_user_roles,
)

REPORT = {}
ADMIN = "Administrator"
PASSWORD = "AcceptancePass123!"
USERS = {
	"admin_a": "accept-admin-a@example.com",
	"supervisor_a": "accept-supervisor-a@example.com",
	"agent_a": "accept-agent-a@example.com",
	"admin_b": "accept-admin-b@example.com",
}
TENANTS = {
	"a": {
		"slug": "accept-a",
		"name": "Acceptance A",
		"sip_domain": "accept-a.localhost",
		"context": "accept_a",
	},
	"b": {
		"slug": "accept-b",
		"name": "Acceptance B",
		"sip_domain": "accept-b.localhost",
		"context": "accept_b",
	},
}


def record(key, value):
	REPORT[key] = value


def ensure_user(email, first_name):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first_name,
				"enabled": 1,
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
	else:
		user = frappe.get_doc("User", email)
		if not user.enabled:
			user.enabled = 1
			user.save(ignore_permissions=True)
	return email


def ensure_tenant(spec):
	if not frappe.db.exists("FS Tenant", spec["slug"]):
		frappe.get_doc(
			{
				"doctype": "FS Tenant",
				"tenant_name": spec["name"],
				"slug": spec["slug"],
				"enabled": 1,
				"sip_domain": spec["sip_domain"],
				"default_context": spec["context"],
				"outbound_caller_id": "+14155550199",
				"hold_music_file": "local_stream://moh",
				"description": "Live acceptance fixture.",
			}
		).insert(ignore_permissions=True)
	else:
		doc = frappe.get_doc("FS Tenant", spec["slug"])
		doc.sip_domain = spec["sip_domain"]
		doc.default_context = spec["context"]
		doc.enabled = 1
		doc.save(ignore_permissions=True)
	return spec["slug"]


def set_member(tenant, user, role):
	doc = frappe.get_doc("FS Tenant", tenant)
	row = next((row for row in doc.members or [] if row.user == user), None)
	if row:
		row.role = role
		row.enabled = 1
	else:
		doc.append("members", {"user": user, "role": role, "enabled": 1})
	doc.save(ignore_permissions=True)


def ensure_extension(name, tenant, context, user, display):
	if not frappe.db.exists("FS Extension", name):
		frappe.get_doc(
			{
				"doctype": "FS Extension",
				"extension": name,
				"tenant": tenant,
				"context": context,
				"user": user,
				"display_name": display,
				"sip_password": PASSWORD,
				"enabled": 1,
				"agent_status": "Available",
			}
		).insert(ignore_permissions=True)
	return name


def ensure_queue(name, tenant):
	if not frappe.db.exists("FS Queue", name):
		frappe.get_doc(
			{
				"doctype": "FS Queue",
				"queue_name": name,
				"tenant": tenant,
				"display_name": "Acceptance support",
				"enabled": 1,
				"strategy": "longest-idle-agent",
				"max_wait_seconds": 180,
				"music_on_hold": "local_stream://moh",
				"agents": [
					{
						"doctype": "FS Queue Agent",
						"extension": "7101",
						"level": 1,
						"position": 1,
					}
				],
			}
		).insert(ignore_permissions=True)
	return name


def ensure_flow(title, tenant, context):
	graph = {
		"nodes": [
			{
				"id": "answer",
				"type": "fs-node",
				"position": {"x": 100, "y": 80},
				"data": {"label": "Answer", "application": "answer", "data": ""},
			},
			{
				"id": "hangup",
				"type": "fs-node",
				"position": {"x": 100, "y": 240},
				"data": {"label": "Hang up", "application": "hangup", "data": ""},
			},
		],
		"edges": [{"id": "e1", "source": "answer", "target": "hangup"}],
	}
	if frappe.db.exists("FS Dialplan", title):
		doc = frappe.get_doc("FS Dialplan", title)
		doc.tenant = tenant
		doc.context = context
		doc.graph_format = "raw"
		doc.graph = json.dumps(graph)
		doc.enabled = 1
	else:
		doc = frappe.get_doc(
			{
				"doctype": "FS Dialplan",
				"title": title,
				"tenant": tenant,
				"context": context,
				"extension_name": title.lower().replace(" ", "_"),
				"destination_number": r"^\+?1415555010[12]$",
				"priority": 10,
				"enabled": 1,
				"graph_format": "raw",
				"graph": json.dumps(graph),
				"description": "Live acceptance fixture.",
			}
		).insert(ignore_permissions=True)
	doc.save(ignore_permissions=True)
	publish_flow(doc, note="live acceptance", published_by=ADMIN)
	doc.save(ignore_permissions=True)
	return doc.name


def ensure_did(number, tenant, flow):
	key = did_key(number)
	existing = None
	for row in frappe.get_all("FS DID", fields=["name", "number"]):
		if did_key(row.number) == key:
			existing = row.name
			break
	if existing:
		doc = frappe.get_doc("FS DID", existing)
		doc.tenant = tenant
		doc.flow = flow
		doc.enabled = 1
		doc.save(ignore_permissions=True)
		return existing
	return (
		frappe.get_doc(
			{
				"doctype": "FS DID",
				"number": number,
				"tenant": tenant,
				"flow": flow,
				"enabled": 1,
				"description": "Live acceptance fixture.",
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


frappe.set_user(ADMIN)
# bench console does not always initialise the user's locale; Frappe's version
# diff formatter needs one when it formats Datetime fields.
frappe.local.lang = frappe.local.lang or "en"
ensure_default_tenant()
ensure_tenant_roles()

for email, first_name in (
	(USERS["admin_a"], "Acceptance Admin A"),
	(USERS["supervisor_a"], "Acceptance Supervisor A"),
	(USERS["agent_a"], "Acceptance Agent A"),
	(USERS["admin_b"], "Acceptance Admin B"),
):
	ensure_user(email, first_name)

tenant_a = ensure_tenant(TENANTS["a"])
tenant_b = ensure_tenant(TENANTS["b"])
set_member(tenant_a, USERS["admin_a"], "Admin")
set_member(tenant_a, USERS["supervisor_a"], "Supervisor")
set_member(tenant_a, USERS["agent_a"], "Agent")
set_member(tenant_b, USERS["admin_b"], "Admin")
for email in USERS.values():
	sync_user_roles(email)
frappe.clear_cache()

ext_a = ensure_extension("7101", tenant_a, "accept_a", USERS["agent_a"], "Acceptance Agent A")
ext_b = ensure_extension("7201", tenant_b, "accept_b", USERS["admin_b"], "Acceptance Admin B")
ext_a_doc = frappe.get_doc("FS Extension", ext_a)
ext_b_doc = frappe.get_doc("FS Extension", ext_b)
ensure_queue("accept_support", tenant_a)
flow_a = ensure_flow("Acceptance A inbound", tenant_a, "accept_a")
flow_b = ensure_flow("Acceptance B inbound", tenant_b, "accept_b")
did_a = ensure_did("+14155550101", tenant_a, flow_a)
did_b = ensure_did("+14155550102", tenant_b, flow_b)
did_a_doc = frappe.get_doc("FS DID", did_a)
did_b_doc = frappe.get_doc("FS DID", did_b)

frappe.db.commit()
invalidate_all()

record("roles", {role: bool(frappe.db.exists("Role", role)) for role in (
	"FS Switch Admin",
	"FS Switch Supervisor",
	"FS Switch Agent",
)})
record("doctypes", {doctype: bool(frappe.db.exists("DocType", doctype)) for doctype in (
	"FS Tenant",
	"FS Tenant Member",
	"FS DID",
)})
record("dids", {"a": did_a, "b": did_b, "normalized": normalize_did("+1 (415) 555-0101")})
record("flows", {"a": flow_a, "b": flow_b})
record("published", {
	"a": frappe.db.get_value("FS Dialplan", flow_a, "publish_status"),
	"b": frappe.db.get_value("FS Dialplan", flow_b, "publish_status"),
})

record("xml", {
	"directory_has_a": "7101" in serve_directory("accept-a.localhost"),
	"directory_hides_b": "7201" not in serve_directory("accept-a.localhost"),
	"dialplan_has_a": "acceptance_a_inbound" in serve_dialplan("accept_a"),
	"dialplan_hides_b": "acceptance_b_inbound" not in serve_dialplan("accept_a"),
	"callcenter_has_a": "accept_support@accept_a" in serve_callcenter(),
	"secret_cached": bool(expected_secret_hash()),
})

# Role and row-level checks.
frappe.set_user(USERS["admin_a"])
record("admin_a", {
	"roles": [role for role in frappe.get_roles() if role.startswith("FS Switch")],
	"tenants": [row.name for row in frappe.get_list("FS Tenant", fields=["name"])],
	"extensions": [row.name for row in frappe.get_list("FS Extension", fields=["name"])],
})

frappe.set_user(USERS["supervisor_a"])
record("supervisor_a", {
	"roles": [role for role in frappe.get_roles() if role.startswith("FS Switch")],
	"tenants": [row.name for row in frappe.get_list("FS Tenant", fields=["name"])],
	"extensions": [row.name for row in frappe.get_list("FS Extension", fields=["name"])],
	"extension_write": frappe.has_permission("FS Extension", "write", doc=ext_a_doc),
	"did_read": frappe.has_permission("FS DID", "read", doc=did_a_doc),
})

frappe.set_user(USERS["admin_b"])
record("admin_b", {
	"roles": [role for role in frappe.get_roles() if role.startswith("FS Switch")],
	"tenants": [row.name for row in frappe.get_list("FS Tenant", fields=["name"])],
	"extensions": [row.name for row in frappe.get_list("FS Extension", fields=["name"])],
	"dids": [row.name for row in frappe.get_list("FS DID", fields=["name"])],
})

frappe.set_user(USERS["agent_a"])
record("agent_a", {
	"roles": [role for role in frappe.get_roles() if role.startswith("FS Switch")],
	"own_extension_read": frappe.has_permission("FS Extension", "read", doc=ext_a_doc),
	"other_extension_read": frappe.has_permission("FS Extension", "read", doc=ext_b_doc),
	"did_read": frappe.has_permission("FS DID", "read", doc=did_a_doc),
	"softphone": (
		frappe.get_attr("fs_switch.api.get_softphone_config")(tenant=tenant_a) or {}
	).get("extension"),
	"status_change": frappe.get_attr("fs_switch.api.set_my_agent_status")(
		"On Break", tenant=tenant_a
	),
})
frappe.get_attr("fs_switch.api.set_my_agent_status")("Available", tenant=tenant_a)
frappe.db.commit()
frappe.set_user(ADMIN)
record("realtime", {
	"a_recipients": _live_users(tenant_a),
	"b_recipients": _live_users(tenant_b),
})

print("LIVE_ACCEPTANCE=" + json.dumps(REPORT, default=str, indent=2))
