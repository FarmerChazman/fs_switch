"""Publish existing valid Flows once, so upgrading does not break routing."""

import frappe

from fs_switch.publish import publish_flow


def execute():
	for name in frappe.get_all("FS Dialplan", pluck="name"):
		doc = frappe.get_doc("FS Dialplan", name)
		if doc.published_on or not doc.graph:
			continue
		try:
			publish_flow(doc, note="Initial publish during upgrade", published_by="Administrator")
			doc.save(ignore_permissions=True)
		except Exception as exc:
			frappe.log_error(
				title=f"FS Switch publish migration {name}",
				message=str(exc),
			)
	frappe.db.commit()
