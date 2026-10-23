"""Tenant helpers.

The alpha is single-tenant: every routing label resolves to ``default``. The
DocTypes and cache keys already carry a tenant so the multi-tenant UI can be
added without changing the call-setup contract.
"""

from __future__ import annotations

DEFAULT_TENANT = "default"
DEFAULT_TENANT_NAME = "Default"


def default_tenant() -> str:
	return DEFAULT_TENANT


def tenant_or_default(value) -> str:
	return str(value or "").strip() or DEFAULT_TENANT


def fixed_tenant(doc) -> str:
	"""Keep an existing document in its Tenant; a Tenant move is not a draft edit."""
	before = doc.get_doc_before_save() if hasattr(doc, "get_doc_before_save") else None
	if before is not None:
		return tenant_or_default(getattr(before, "tenant", None))
	return tenant_or_default(getattr(doc, "tenant", None))


def ensure_default_tenant():
	"""Create the default Tenant on install or upgrade, if it is missing."""
	import frappe

	if frappe.db.exists("FS Tenant", DEFAULT_TENANT):
		return DEFAULT_TENANT

	settings = frappe.get_single("FS Switch Settings")
	frappe.get_doc(
		{
			"doctype": "FS Tenant",
			"tenant_name": DEFAULT_TENANT_NAME,
			"slug": DEFAULT_TENANT,
			"enabled": 1,
			"sip_domain": getattr(settings, "sip_domain", None) or "",
			"default_context": getattr(settings, "default_context", None) or "default",
			"description": "Default tenant created by FS Switch.",
		}
	).insert(ignore_permissions=True)
	return DEFAULT_TENANT
