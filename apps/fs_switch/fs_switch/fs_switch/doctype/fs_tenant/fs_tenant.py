import frappe
from frappe.model.document import Document

from fs_switch.call_setup import invalidate_tenant_after_commit
from fs_switch.tenants import (
	configured_default_tenant,
	normalize_context,
	normalize_domain,
	normalize_slug,
	sync_user_roles,
)


class FSTenant(Document):
	def validate(self):
		self.tenant_name = (self.tenant_name or "").strip()
		self.slug = normalize_slug(self.slug)
		if not self.slug:
			frappe.throw("A tenant slug is required.")
		if not self.is_new() and self.slug != self.name:
			frappe.throw("Tenant slug cannot be changed after creation.")
		self.sip_domain = normalize_domain(self.sip_domain)
		self.default_context = normalize_context(self.default_context) or "default"
		if self.name == configured_default_tenant() and not self.enabled:
			frappe.throw("The default Tenant cannot be disabled.")
		self._validate_members()
		self._validate_unique_labels()

	def _validate_members(self):
		seen = set()
		for row in self.members or []:
			row.role = row.role or "Agent"
			if row.role not in ("Admin", "Supervisor", "Agent"):
				frappe.throw(f"Unsupported Tenant role: {row.role}")
			if not row.user:
				frappe.throw("Every Tenant member needs a user.")
			if not frappe.db.exists("User", row.user):
				frappe.throw(f"User {row.user} does not exist.")
			if row.user in seen:
				frappe.throw(f"User {row.user} appears more than once in this Tenant.")
			seen.add(row.user)
			row.enabled = 0 if str(row.enabled).strip().lower() in ("", "0", "false") else 1

	def _validate_unique_labels(self):
		others = frappe.get_all(
			"FS Tenant",
			filters={"enabled": 1, "name": ["!=", self.name or ""]},
			fields=["name", "sip_domain", "default_context"],
		)
		for row in others:
			if self.sip_domain and normalize_domain(row.sip_domain) == self.sip_domain:
				frappe.throw(f"SIP domain {self.sip_domain} already belongs to Tenant {row.name}.")
			if normalize_context(row.default_context) == self.default_context:
				frappe.throw(
					f"Context {self.default_context} already belongs to Tenant {row.name}."
				)

	def on_update(self):
		before = self.get_doc_before_save()
		users = {row.user for row in self.members or [] if row.user}
		if before:
			users.update(row.user for row in before.members or [] if row.user)
		invalidate_tenant_after_commit()
		self._sync_roles_after_commit(users)

	def on_trash(self):
		if self.name == configured_default_tenant():
			frappe.throw("The default Tenant cannot be deleted.")
		self._deleted_users = {row.user for row in self.members or [] if row.user}

	def after_delete(self):
		invalidate_tenant_after_commit()
		self._sync_roles_after_commit(getattr(self, "_deleted_users", set()))

	def _sync_roles_after_commit(self, users):
		def run():
			for user in users:
				if user:
					sync_user_roles(user)

		try:
			frappe.db.after_commit.add(run)
		except Exception:
			run()
