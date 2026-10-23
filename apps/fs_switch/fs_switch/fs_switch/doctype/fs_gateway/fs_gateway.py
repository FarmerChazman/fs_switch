from frappe.model.document import Document

from fs_switch.tenants import fixed_tenant


class FSGateway(Document):
	def validate(self):
		self.tenant = fixed_tenant(self)
