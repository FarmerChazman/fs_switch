from frappe.model.document import Document

from fs_switch.call_setup import invalidate_after_commit
from fs_switch.tenants import fixed_tenant


class FSExtension(Document):
	def validate(self):
		self.tenant = fixed_tenant(self)

	def on_update(self):
		# The directory carries SIP credentials; callcenter.conf carries the
		# agent status. Both are read by FreeSWITCH during call setup.
		invalidate_after_commit("directory", "callcenter")

	def after_delete(self):
		invalidate_after_commit("directory", "callcenter")
