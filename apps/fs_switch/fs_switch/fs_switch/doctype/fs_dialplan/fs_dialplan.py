import frappe
from frappe.model.document import Document

from fs_switch.call_setup import invalidate_after_commit
from fs_switch.dialplan import DialplanError, compile_extension
from fs_switch.flow import FlowError
from fs_switch.publish import published_status
from fs_switch.tenants import (
	assert_tenant_value_unique,
	fixed_tenant,
	normalize_context,
	tenant_scoped_name,
)

SERVING_FIELDS = (
	"title",
	"tenant",
	"enabled",
	"published_version",
	"published_context",
	"published_tenant",
	"published_priority",
	"published_xml",
)

PUBLISHED_FIELDS = (
	"published_version",
	"published_on",
	"published_by",
	"published_xml",
	"published_graph",
	"published_graph_format",
	"published_context",
	"published_tenant",
	"published_priority",
)

PUBLISHED_DEFAULTS = {
	"published_version": 0,
	"published_on": None,
	"published_by": None,
	"published_xml": "",
	"published_graph": "",
	"published_graph_format": "",
	"published_context": "",
	"published_tenant": "",
	"published_priority": 0,
}


class FSDialplan(Document):
	def autoname(self):
		self.name = tenant_scoped_name(fixed_tenant(self), self.title)

	def validate(self):
		self.tenant = fixed_tenant(self)
		self.title = str(self.title or "").strip()
		assert_tenant_value_unique(
			"FS Dialplan",
			self.tenant,
			"title",
			self.title,
			None if self.is_new() else self.name,
		)
		tenant_context = normalize_context(
			frappe.db.get_value("FS Tenant", self.tenant, "default_context")
		)
		self.context = normalize_context(self.context) or tenant_context or "default"
		if tenant_context and self.context != tenant_context:
			frappe.throw(
				f"Context {self.context} does not belong to Tenant {self.tenant}. "
				f"Use {tenant_context}."
			)
		# Publishing and rollback are the only ways to change the served version.
		# A normal save must not let a client inject published XML or history rows.
		if not getattr(getattr(self, "flags", None), "publishing", False):
			before = self.get_doc_before_save()
			if before:
				for field in PUBLISHED_FIELDS:
					setattr(self, field, getattr(before, field, None))
				self.versions = before.versions
			elif self.is_new():
				for field, default in PUBLISHED_DEFAULTS.items():
					setattr(self, field, default)
				self.versions = []
		if not self.graph:
			self.compiled_xml = ""
		else:
			try:
				self.compiled_xml = compile_extension(self)
			except (DialplanError, FlowError) as exc:
				frappe.throw(str(exc))
		self.publish_status = published_status(self)

	def on_update(self):
		# Draft-only edits do not change what FreeSWITCH is served, so leave
		# the cache warm. Publish, rollback and enable/disable do.
		before = self.get_doc_before_save()
		if before is None or any(
			getattr(self, field, None) != getattr(before, field, None)
			for field in SERVING_FIELDS
		):
			invalidate_after_commit("dialplan")

	def after_delete(self):
		invalidate_after_commit("dialplan")
