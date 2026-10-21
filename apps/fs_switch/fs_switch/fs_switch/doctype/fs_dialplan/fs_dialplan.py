import frappe
from frappe.model.document import Document

from fs_switch.dialplan import DialplanError, compile_extension


class FSDialplan(Document):
	def validate(self):
		if not self.graph:
			self.compiled_xml = ""
			return
		try:
			self.compiled_xml = compile_extension(self)
		except DialplanError as exc:
			frappe.throw(str(exc))
