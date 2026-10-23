from frappe.model.document import Document

from fs_switch.tenants import (
	assert_tenant_value_unique,
	fixed_tenant,
	tenant_scoped_name,
)


class FSGateway(Document):
	def autoname(self):
		self.name = tenant_scoped_name(fixed_tenant(self), self.gateway_name)

	def validate(self):
		self.tenant = fixed_tenant(self)
		self.gateway_name = str(self.gateway_name or "").strip()
		assert_tenant_value_unique(
			"FS Gateway",
			self.tenant,
			"gateway_name",
			self.gateway_name,
			None if self.is_new() else self.name,
		)
