"""Move the natural-key DocTypes onto Tenant-qualified names."""

import frappe

from fs_switch.tenants import tenant_scoped_name


SCOPED_DOCTYPES = (
	("FS Extension", "extension"),
	("FS Queue", "queue_name"),
	("FS Gateway", "gateway_name"),
	("FS Dialplan", "title"),
)


def execute():
	for doctype, field in SCOPED_DOCTYPES:
		# The patch may run before the schema sync. With the old
		# ``autoname = field:<natural_key>`` rule, rename_doc would overwrite the
		# natural key with the new document name. Switch the meta to hash first.
		frappe.db.set_value(
			"DocType",
			doctype,
			"autoname",
			"hash",
			update_modified=False,
		)
		frappe.clear_cache(doctype=doctype)
		rows = frappe.get_all(
			doctype,
			fields=["name", "tenant", field],
			order_by="creation asc",
		)
		for row in rows:
			new_name = tenant_scoped_name(row.get("tenant"), row.get(field) or row.get("name"))
			if not new_name or new_name == row.get("name"):
				continue
			if frappe.db.exists(doctype, new_name):
				frappe.log_error(
					title="FS Switch tenant-scoped name migration",
					message=f"Could not rename {doctype} {row.get('name')} to {new_name}: target exists.",
				)
				continue
			frappe.rename_doc(
				doctype,
				row.get("name"),
				new_name,
				force=True,
			)
