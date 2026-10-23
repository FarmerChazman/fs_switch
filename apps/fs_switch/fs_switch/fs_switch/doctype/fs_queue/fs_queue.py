import frappe
from frappe.model.document import Document

from fs_switch.call_setup import invalidate_after_commit
from fs_switch.tenants import fixed_tenant, tenant_or_default


class FSQueue(Document):
	def validate(self):
		self.tenant = fixed_tenant(self)
		if self.backup_queue:
			backup_tenant = frappe.db.get_value("FS Queue", self.backup_queue, "tenant")
			if backup_tenant and tenant_or_default(backup_tenant) != self.tenant:
				frappe.throw("The backup queue must belong to the same tenant.")
		for row in self.agents or []:
			extension_tenant = frappe.db.get_value("FS Extension", row.extension, "tenant")
			if extension_tenant and tenant_or_default(extension_tenant) != self.tenant:
				frappe.throw(f"Extension {row.extension} belongs to another tenant.")

	def on_update(self):
		invalidate_after_commit("callcenter")

	def after_delete(self):
		invalidate_after_commit("callcenter")
