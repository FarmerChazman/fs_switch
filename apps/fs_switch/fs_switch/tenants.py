"""Tenant helpers: routing-label mapping, membership and role sync.

A Tenant owns one SIP domain and one default context. FreeSWITCH routing labels
are resolved to a Tenant; the Tenant then scopes every directory, dialplan and
callcenter query. The mapping is cached with the call-setup documents so a warm
call does not read MariaDB for tenant resolution.

Membership lives on the Tenant as ``FS Tenant Member`` rows. Frappe roles are
global, so the membership role is projected onto three app roles:

    Admin       -> FS Switch Admin       (config, publish, rollback)
    Supervisor  -> FS Switch Supervisor  (live operations, read config)
    Agent       -> FS Switch Agent       (own extension and softphone)

System Manager is the global administrator and needs no membership.
"""

from __future__ import annotations

import hashlib

DEFAULT_TENANT = "default"
MAX_NAME_LENGTH = 140
DEFAULT_TENANT_NAME = "Default"

TENANT_ROLE_ADMIN = "Admin"
TENANT_ROLE_SUPERVISOR = "Supervisor"
TENANT_ROLE_AGENT = "Agent"
TENANT_ROLES = (TENANT_ROLE_ADMIN, TENANT_ROLE_SUPERVISOR, TENANT_ROLE_AGENT)

FS_ROLE_ADMIN = "FS Switch Admin"
FS_ROLE_SUPERVISOR = "FS Switch Supervisor"
FS_ROLE_AGENT = "FS Switch Agent"
FS_ROLES = (FS_ROLE_ADMIN, FS_ROLE_SUPERVISOR, FS_ROLE_AGENT)
ROLE_FOR_TENANT_ROLE = {
	TENANT_ROLE_ADMIN: FS_ROLE_ADMIN,
	TENANT_ROLE_SUPERVISOR: FS_ROLE_SUPERVISOR,
	TENANT_ROLE_AGENT: FS_ROLE_AGENT,
}

TENANT_SCOPED_DOCTYPES = ("FS Dialplan", "FS DID", "FS Extension", "FS Gateway", "FS Queue")
CONFIG_WRITE_ROLES = (TENANT_ROLE_ADMIN,)
CONFIG_READ_ROLES = (TENANT_ROLE_ADMIN, TENANT_ROLE_SUPERVISOR)
LIVE_ROLES = (TENANT_ROLE_ADMIN, TENANT_ROLE_SUPERVISOR)


def default_tenant() -> str:
	return DEFAULT_TENANT


def configured_default_tenant() -> str:
	"""Return the Tenant slug used for unknown routing labels."""
	try:
		frappe = _frappe()
		settings = frappe.get_single("FS Switch Settings")
		return tenant_or_default(getattr(settings, "default_tenant", None))
	except Exception:
		return DEFAULT_TENANT


def tenant_or_default(value) -> str:
	return str(value or "").strip().lower() or DEFAULT_TENANT


def normalize_domain(value) -> str:
	"""Normalize a SIP domain for matching, without touching an optional port."""
	text = str(value or "").strip().lower().rstrip(".")
	if not text:
		return ""
	if text.startswith("["):
		# IPv6 literal, e.g. [2001:db8::1]:5060
		return text
	if text.count(":") == 1:
		host, port = text.rsplit(":", 1)
		if port.isdigit():
			return host
	return text


def normalize_context(value) -> str:
	"""Contexts are case-sensitive in FreeSWITCH; FS Switch stores lowercase."""
	return str(value or "").strip().lower()


def normalize_slug(value) -> str:
	return str(value or "").strip().lower()


def assert_tenant_value_unique(
	doctype: str, tenant, field: str, value, name=None
) -> None:
	"""Reject a duplicate natural key inside one Tenant."""
	value = str(value or "").strip()
	if not value:
		return
	frappe = _frappe()
	filters = {"tenant": tenant_or_default(tenant), field: value}
	if name:
		filters["name"] = ["!=", name]
	if frappe.db.exists(doctype, filters):
		frappe.throw(
			f"{doctype} {value!r} already exists in Tenant {tenant_or_default(tenant)}."
		)


def tenant_scoped_name(tenant, value) -> str:
	"""Return a stable, Tenant-qualified document name.

	The natural key stays readable for support work, while the Tenant prefix
	makes extension numbers, queue names, gateway names and Flow titles unique
	inside one Tenant instead of globally.
	"""
	prefix = f"{tenant_or_default(tenant)}::"
	key = str(value or "").strip() or "untitled"
	available = MAX_NAME_LENGTH - len(prefix)
	if available <= 0:
		digest = hashlib.sha1(f"{prefix}{key}".encode("utf-8")).hexdigest()[:8]
		return f"{prefix[: MAX_NAME_LENGTH - 9]}#{digest}"
	if len(key) > available:
		digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
		key = f"{key[: max(0, available - 9)]}#{digest}"
	return prefix + key


def fixed_tenant(doc) -> str:
	"""Keep an existing document in its Tenant; a Tenant move is not a draft edit."""
	before = doc.get_doc_before_save() if hasattr(doc, "get_doc_before_save") else None
	if before is not None:
		return tenant_or_default(getattr(before, "tenant", None))
	tenant = getattr(doc, "tenant", None)
	return tenant_or_default(tenant) if tenant else configured_default_tenant()


def tenant_map_from_rows(rows, default=None) -> dict:
	"""Build the cached routing map from FS Tenant rows.

	The function is pure so it can be tested without a Frappe site. Duplicate
	labels are resolved first-wins; the FS Tenant controller rejects duplicates
	at save time.
	"""
	domains: dict[str, str] = {}
	contexts: dict[str, str] = {}
	for row in rows or []:
		if isinstance(row, dict):
			enabled = row.get("enabled", 1)
			name = row.get("name") or row.get("slug")
			sip_domain = row.get("sip_domain")
			default_context = row.get("default_context")
		else:
			enabled = getattr(row, "enabled", 1)
			name = getattr(row, "name", None) or getattr(row, "slug", None)
			sip_domain = getattr(row, "sip_domain", None)
			default_context = getattr(row, "default_context", None)
		if not enabled:
			continue
		tenant = tenant_or_default(name)
		domain = normalize_domain(sip_domain)
		context = normalize_context(default_context)
		if domain and domain not in domains:
			domains[domain] = tenant
		if context and context not in contexts:
			contexts[context] = tenant
	return {
		"default": tenant_or_default(default),
		"domains": domains,
		"contexts": contexts,
	}


def resolve_tenant_from_map(mapping, domain=None, context=None) -> str:
	"""Resolve a routing label to a Tenant, falling back to the default Tenant.

	A caller normally supplies one label: the domain for directory lookups and
	the context for dialplan and callcenter lookups. When both are supplied and
	disagree, the context wins because it is the routing label that selected the
	dialplan.
	"""
	mapping = mapping or {}
	domain_key = normalize_domain(domain)
	context_key = normalize_context(context)
	if context_key and context_key in (mapping.get("contexts") or {}):
		return tenant_or_default(mapping["contexts"][context_key])
	if domain_key and domain_key in (mapping.get("domains") or {}):
		return tenant_or_default(mapping["domains"][domain_key])
	return tenant_or_default(mapping.get("default"))


def _frappe():
	import frappe

	return frappe


def _session_user(user=None) -> str:
	return user or _frappe().session.user


def is_system_manager(user=None) -> bool:
	return "System Manager" in _frappe().get_roles(_session_user(user))


def memberships(user=None) -> list[dict]:
	"""Return enabled Tenant memberships for a user."""
	frappe = _frappe()
	user = _session_user(user)
	if not user or user == "Guest":
		return []
	rows = frappe.get_all(
		"FS Tenant Member",
		filters={"user": user, "enabled": 1},
		fields=["parent", "role"],
	)
	if not rows:
		return []
	tenants = frappe.get_all(
		"FS Tenant",
		filters={"name": ["in", [row.parent for row in rows]], "enabled": 1},
		fields=["name", "tenant_name", "sip_domain", "default_context"],
	)
	by_name = {row.name: row for row in tenants}
	result = []
	for row in rows:
		tenant = by_name.get(row.parent)
		if not tenant:
			continue
		result.append(
			{
				"tenant": tenant.name,
				"tenant_name": tenant.tenant_name or tenant.name,
				"role": row.role or TENANT_ROLE_AGENT,
				"sip_domain": tenant.sip_domain or "",
				"default_context": tenant.default_context or "default",
			}
		)
	return result


def accessible_tenants(user=None) -> list[dict]:
	"""Return Tenants a user may read, with the user's role in each."""
	frappe = _frappe()
	user = _session_user(user)
	if is_system_manager(user):
		rows = frappe.get_all(
			"FS Tenant",
			filters={"enabled": 1},
			fields=["name", "tenant_name", "sip_domain", "default_context"],
			order_by="tenant_name asc",
		)
		return [
			{
				"tenant": row.name,
				"tenant_name": row.tenant_name or row.name,
				"role": "System Manager",
				"sip_domain": row.sip_domain or "",
				"default_context": row.default_context or "default",
			}
			for row in rows
		]
	return sorted(memberships(user), key=lambda row: row["tenant_name"].lower())


def role_for_tenant(user, tenant) -> str | None:
	frappe = _frappe()
	user = _session_user(user)
	if not user or user == "Guest":
		return None
	if is_system_manager(user):
		return "System Manager"
	role = frappe.db.get_value(
		"FS Tenant Member",
		{"parent": tenant, "user": user, "enabled": 1},
		"role",
	)
	return role or None


def can_read_tenant(user, tenant) -> bool:
	return role_for_tenant(user, tenant) is not None


def can_write_tenant(user, tenant) -> bool:
	return role_for_tenant(user, tenant) in ("System Manager", *CONFIG_WRITE_ROLES)


def can_supervise_tenant(user, tenant) -> bool:
	return role_for_tenant(user, tenant) in ("System Manager", *LIVE_ROLES)


def tenant_roles_for(user=None) -> dict[str, str]:
	return {row["tenant"]: row["role"] for row in accessible_tenants(user)}


def ensure_tenant_roles():
	"""Create the app roles on install or migrate and point them at the console."""
	frappe = _frappe()
	for role in FS_ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc(
				{
					"doctype": "Role",
					"role_name": role,
					"desk_access": 1,
					"is_custom": 1,
					"home_page": "/fs-switch",
				}
			).insert(ignore_permissions=True)
		else:
			role_doc = frappe.get_doc("Role", role)
			if role_doc.home_page != "/fs-switch":
				role_doc.home_page = "/fs-switch"
				role_doc.save(ignore_permissions=True)
	return FS_ROLES


def sync_user_roles(user):
	"""Project a user's Tenant memberships onto the three app roles."""
	frappe = _frappe()
	if not user or user in ("Guest", "Administrator"):
		return []
	if not frappe.db.exists("User", user):
		return []
	roles = {row["role"] for row in memberships(user)}
	wanted = {ROLE_FOR_TENANT_ROLE[role] for role in roles if role in ROLE_FOR_TENANT_ROLE}
	user_doc = frappe.get_doc("User", user)
	current = {row.role for row in user_doc.roles or []}
	to_add = wanted - current
	to_remove = {role for role in FS_ROLES if role in current and role not in wanted}
	if to_add:
		user_doc.add_roles(*sorted(to_add))
	if to_remove:
		user_doc.remove_roles(*sorted(to_remove))
	return sorted(wanted)


def sync_all_user_roles():
	"""Reconcile roles for every user referenced by a Tenant membership."""
	frappe = _frappe()
	users = frappe.db.sql(
		"select distinct user from `tabFS Tenant Member` "
		"where user is not null and user != ''",
		pluck=True,
	)
	for user in users:
		if user:
			sync_user_roles(user)
	return users


def users_for_tenant(tenant) -> list[str]:
	frappe = _frappe()
	return frappe.get_all(
		"FS Tenant Member",
		filters={"parent": tenant},
		pluck="user",
	)


def _create_tenant(slug, settings):
	frappe = _frappe()
	tenant_name = (
		DEFAULT_TENANT_NAME
		if slug == DEFAULT_TENANT
		else slug.replace("-", " ").title()
	)
	frappe.get_doc(
		{
			"doctype": "FS Tenant",
			"tenant_name": tenant_name,
			"slug": slug,
			"enabled": 1,
			"sip_domain": getattr(settings, "sip_domain", None) or "",
			"default_context": getattr(settings, "default_context", None) or "default",
			"description": "Default tenant created by FS Switch.",
		}
	).insert(ignore_permissions=True)
	return slug


def _backfill_default_tenant(settings):
	frappe = _frappe()
	# The first alpha created the Tenant before the container wrote its
	# settings, so a blank SIP domain is backfilled once.
	current = frappe.db.get_value("FS Tenant", DEFAULT_TENANT, "sip_domain")
	if not current and getattr(settings, "sip_domain", None):
		frappe.db.set_value(
			"FS Tenant",
			DEFAULT_TENANT,
			"sip_domain",
			settings.sip_domain,
			update_modified=False,
		)


def ensure_default_tenant():
	"""Ensure the configured default Tenant exists on install or upgrade."""
	frappe = _frappe()
	settings = frappe.get_single("FS Switch Settings")
	configured = tenant_or_default(getattr(settings, "default_tenant", None))
	configured_exists = frappe.db.exists("FS Tenant", configured)
	default_exists = frappe.db.exists("FS Tenant", DEFAULT_TENANT)

	if configured_exists:
		if not frappe.db.get_value("FS Tenant", configured, "enabled"):
			frappe.db.set_value(
				"FS Tenant", configured, "enabled", 1, update_modified=False
			)
		if configured == DEFAULT_TENANT or default_exists:
			_backfill_default_tenant(settings)
		return configured

	if default_exists:
		# The setting points at a missing Tenant. Repair it instead of routing
		# unknown labels to a Tenant that does not exist.
		frappe.db.set_value(
			"FS Switch Settings",
			"FS Switch Settings",
			"default_tenant",
			DEFAULT_TENANT,
			update_modified=False,
		)
		_backfill_default_tenant(settings)
		return DEFAULT_TENANT

	# Fresh install, or a database with no usable fallback. The environment may
	# have named the first Tenant something other than "default".
	return _create_tenant(configured, settings)


def after_migrate():
	"""Keep the role table and membership projections in sync after a migrate."""
	from fs_switch.call_setup import invalidate_all

	ensure_default_tenant()
	ensure_tenant_roles()
	sync_all_user_roles()
	try:
		website = _frappe().get_single("Website Settings")
		if not website.home_page:
			website.home_page = "fs-switch"
			website.save(ignore_permissions=True)
	except Exception:
		# A site may not have Website Settings during a partial bootstrap.
		pass
	invalidate_all()
