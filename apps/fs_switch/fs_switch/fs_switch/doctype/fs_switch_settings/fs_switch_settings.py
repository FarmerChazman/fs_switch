from frappe.model.document import Document

from fs_switch.call_setup import invalidate_all_after_commit
from fs_switch.tenants import tenant_or_default


class FSSwitchSettings(Document):
	def validate(self):
		self.default_tenant = tenant_or_default(self.default_tenant)

	def on_update(self):
		# Settings feed every handler: the default context, the main DID, the
		# internal-call bridge, hold music, the SIP domain and the shared secret.
		invalidate_all_after_commit()
