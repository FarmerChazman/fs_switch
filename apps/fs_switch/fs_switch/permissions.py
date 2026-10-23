"""Row-level Tenant permissions for Frappe DocTypes and whitelisted methods.

DocType role permissions grant the capability (for example, ``FS Switch Admin``
may write). These hooks narrow that capability to the Tenants where the user
actually has the matching membership role. System Manager is the global
override.
"""

from __future__ import annotations

import frappe

from fs_switch.tenants import (
	CONFIG_READ_ROLES,
	CONFIG_WRITE_ROLES,
	LIVE_ROLES,
	TENANT_ROLE_AGENT,
	accessible_tenants,
	can_read_tenant,
	can_supervise_tenant,
	can_write_tenant,
	is_system_manager,
	memberships,
	role_for_tenant,
)

TENANT_DOCTYPE = "FS Tenant"
TENANT_SCOPED = ("FS Dialplan", "FS DID", "FS Extension", "FS Gateway", "FS Queue")


def _user(user=None):
	return user or frappe.session.user


def _table(doctype):
	return f"`tab{doctype}`"


def _in(values):
	if not values:
		return ""
	return ", ".join(frappe.db.escape(value) for value in sorted(set(values)))


def _tenant_condition(user, roles):
	rows = [row for row in memberships(user) if row["role"] in roles]
	return [row["tenant"] for row in rows]


def tenant_query_conditions(user=None, doctype=None):
	"""Filter Tenant lists to the caller's config-readable memberships."""
	user = _user(user)
	if is_system_manager(user):
		return ""
	tenants = [
		row["tenant"]
		for row in memberships(user)
		if row["role"] in CONFIG_READ_ROLES
	]
	values = _in(tenants)
	if not values:
		return "1=0"
	return f"{_table(TENANT_DOCTYPE)}.`name` in ({values})"


def scoped_query_conditions(user=None, doctype=None):
	"""Filter config lists to readable Tenants, plus an Agent's own extension."""
	user = _user(user)
	if is_system_manager(user):
		return ""
	doctype = doctype or ""
	if doctype not in TENANT_SCOPED:
		return ""
	if doctype == "FS Extension":
		conditions = []
		tenants = _tenant_condition(user, CONFIG_READ_ROLES)
		if tenants:
			conditions.append(f"{_table(doctype)}.`tenant` in ({_in(tenants)})")
		agent_tenants = _tenant_condition(user, (TENANT_ROLE_AGENT,))
		if agent_tenants:
			conditions.append(
				f"({_table(doctype)}.`tenant` in ({_in(agent_tenants)}) "
				f"and {_table(doctype)}.`user` = {frappe.db.escape(user)})"
			)
		return f"({' or '.join(conditions)})" if conditions else "1=0"
	tenants = _tenant_condition(user, CONFIG_READ_ROLES)
	if not tenants:
		return "1=0"
	return f"{_table(doctype)}.`tenant` in ({_in(tenants)})"


def tenant_has_permission(doc, ptype=None, user=None, debug=False):
	"""Deny access outside a user's Tenant membership or Agent scope."""
	user = _user(user)
	if is_system_manager(user):
		return True
	tenant = getattr(doc, "tenant", None)
	ptype = ptype or "read"
	role = role_for_tenant(user, tenant) if tenant else None
	if ptype in ("read", "select", "report", "export", "print", "email", "share"):
		return role in ("System Manager", *CONFIG_READ_ROLES)
	if ptype in ("write", "create", "delete", "submit", "cancel", "amend"):
		return role in ("System Manager", *CONFIG_WRITE_ROLES)
	return False


def tenant_doctype_has_permission(doc, ptype=None, user=None, debug=False):
	"""FS Tenant: read as a config role, write only as a Tenant Admin."""
	user = _user(user)
	if is_system_manager(user):
		return True
	tenant = getattr(doc, "name", None) or getattr(doc, "slug", None)
	ptype = ptype or "read"
	if not tenant:
		return False
	role = role_for_tenant(user, tenant)
	if ptype in ("read", "select", "report", "export", "print", "email", "share"):
		return role in ("System Manager", *CONFIG_READ_ROLES)
	if ptype in ("write", "delete"):
		return role in ("System Manager", *CONFIG_WRITE_ROLES)
	return False


def extension_has_permission(doc, ptype=None, user=None, debug=False):
	"""Agents may read their own extension; config roles follow Tenant scope."""
	user = _user(user)
	if is_system_manager(user):
		return True
	ptype = ptype or "read"
	tenant = getattr(doc, "tenant", None)
	if ptype in ("read", "select", "report", "export", "print", "email", "share"):
		if tenant and can_read_tenant(user, tenant):
			role = role_for_tenant(user, tenant)
			if role in ("System Manager", *CONFIG_READ_ROLES):
				return True
		return bool(tenant and getattr(doc, "user", None) == user and can_read_tenant(user, tenant))
	if ptype in ("write", "create", "delete", "submit", "cancel", "amend"):
		return bool(tenant and can_write_tenant(user, tenant))
	return False


def require_system_manager(message="This action is limited to System Managers."):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw("Please log in.", frappe.PermissionError)
	if not is_system_manager(user):
		frappe.throw(message, frappe.PermissionError)


def require_tenant_read(tenant):
	if not can_read_tenant(frappe.session.user, tenant):
		frappe.throw("You do not have access to this Tenant.", frappe.PermissionError)


def require_tenant_write(tenant):
	if not can_write_tenant(frappe.session.user, tenant):
		frappe.throw(
			"You need the Tenant Admin role to change this Tenant.",
			frappe.PermissionError,
		)


def require_supervisor(tenant=None):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw("Please log in.", frappe.PermissionError)
	if is_system_manager(user):
		return
	if tenant is not None:
		if not can_supervise_tenant(user, tenant):
			frappe.throw("You need a Supervisor or Admin role for this Tenant.", frappe.PermissionError)
		return
	if not any(row["role"] in LIVE_ROLES for row in accessible_tenants(user)):
		frappe.throw("You need a Supervisor or Admin role to view live state.", frappe.PermissionError)
