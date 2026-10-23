"""Create the default Tenant and backfill tenant scope on existing documents."""

import frappe

from fs_switch.tenants import DEFAULT_TENANT, ensure_default_tenant


def execute():
	ensure_default_tenant()

	for doctype in (
		"FS Dialplan",
		"FS Dialplan Version",
		"FS Extension",
		"FS Queue",
		"FS Gateway",
	):
		frappe.db.sql(
			f"update `tab{doctype}` set tenant=%s where tenant is null or tenant=''",
			DEFAULT_TENANT,
		)

	settings = frappe.get_single("FS Switch Settings")
	if not settings.default_tenant:
		settings.default_tenant = DEFAULT_TENANT
		settings.save(ignore_permissions=True)

	frappe.db.sql(
		"update `tabFS Dialplan` set published_tenant=%s "
		"where published_on is not null "
		"and (published_tenant is null or published_tenant='')",
		DEFAULT_TENANT,
	)
