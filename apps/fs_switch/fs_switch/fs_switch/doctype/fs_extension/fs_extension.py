import frappe
from frappe.model.document import Document

from fs_switch.call_setup import invalidate_after_commit
from fs_switch.tenants import fixed_tenant, normalize_context


class FSExtension(Document):
	def validate(self):
		self.tenant = fixed_tenant(self)
		tenant_context = normalize_context(
			frappe.db.get_value("FS Tenant", self.tenant, "default_context")
		)
		self.context = normalize_context(self.context)
		if self.context and tenant_context and self.context != tenant_context:
			frappe.throw(
				f"Extension context {self.context} does not belong to Tenant {self.tenant}."
			)

	def on_update(self):
		# The directory carries SIP credentials; callcenter.conf carries the
		# agent status. Both are read by FreeSWITCH during call setup.
		invalidate_after_commit("directory", "callcenter")

	def after_delete(self):
		invalidate_after_commit("directory", "callcenter")
