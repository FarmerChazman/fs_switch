import frappe
from frappe.model.document import Document

from fs_switch.call_setup import invalidate_all_after_commit


class FSTenant(Document):
	def validate(self):
		self.slug = (self.slug or "").strip()
		if not self.slug:
			frappe.throw("A tenant slug is required.")
		if self.slug != self.slug.lower():
			frappe.throw("Tenant slug must be lowercase.")
		if not self.is_new() and self.slug != self.name:
			frappe.throw("Tenant slug cannot be changed after creation.")

	def on_update(self):
		invalidate_all_after_commit()

	def after_delete(self):
		invalidate_all_after_commit()
