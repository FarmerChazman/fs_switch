import frappe
from frappe.model.document import Document

from fs_switch.call_setup import invalidate_all_after_commit
from fs_switch.tenants import tenant_or_default


class FSSwitchSettings(Document):
	def validate(self):
		self.default_tenant = tenant_or_default(self.default_tenant)
		# On a fresh install the Tenant is created just after the settings are
		# written. On an existing site the setting must point at a real Tenant.
		try:
			tenant_count = frappe.db.count("FS Tenant")
			tenant_exists = frappe.db.exists("FS Tenant", self.default_tenant)
		except Exception:
			tenant_count = 0
			tenant_exists = False
		if self.default_tenant and tenant_count and not tenant_exists:
			frappe.throw(f"Default Tenant {self.default_tenant} does not exist.")

	def on_update(self):
		# Settings feed every handler: the default context, the main DID, the
		# internal-call bridge, hold music, the SIP domain and the shared secret.
		invalidate_all_after_commit()
