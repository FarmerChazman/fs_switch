import frappe
from frappe.model.document import Document

from fs_switch.call_setup import invalidate_after_commit
from fs_switch.dids import did_key, normalize_did
from fs_switch.tenants import fixed_tenant, tenant_or_default


class FSDID(Document):
	def validate(self):
		self.tenant = fixed_tenant(self)
		self.number = normalize_did(self.number)
		if not self.number:
			frappe.throw("A DID / inbound number is required.")
		key = did_key(self.number)
		if not key:
			frappe.throw("A DID must contain digits.")
		for row in frappe.get_all(
			"FS DID",
			filters={"name": ["!=", self.name or ""]},
			fields=["number"],
		):
			if did_key(row.number) == key:
				frappe.throw(f"DID {self.number} is already in the inventory.")
		if self.flow:
			flow_tenant = frappe.db.get_value("FS Dialplan", self.flow, "tenant")
			if flow_tenant and tenant_or_default(flow_tenant) != self.tenant:
				frappe.throw(f"Flow {self.flow} belongs to another Tenant.")

	def on_update(self):
		# The public dialplan is compiled from the DID -> Flow map.
		invalidate_after_commit("dialplan")

	def after_delete(self):
		invalidate_after_commit("dialplan")
