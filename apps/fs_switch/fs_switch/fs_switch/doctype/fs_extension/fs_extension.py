import frappe
from frappe.model.document import Document

from fs_switch.call_setup import invalidate_after_commit
from fs_switch.tenants import (
	assert_tenant_value_unique,
	fixed_tenant,
	normalize_context,
	tenant_scoped_name,
)


class FSExtension(Document):
	def autoname(self):
		self.name = tenant_scoped_name(fixed_tenant(self), self.extension)

	def validate(self):
		self.tenant = fixed_tenant(self)
		self.extension = str(self.extension or "").strip()
		assert_tenant_value_unique(
			"FS Extension",
			self.tenant,
			"extension",
			self.extension,
			None if self.is_new() else self.name,
		)
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
