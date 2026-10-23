"""Serve the documents FreeSWITCH waits on from cache, with last-known-good.

The call-setup path is every XML-curl handler FreeSWITCH blocks on while
routing a call: directory, dialplan and ``callcenter.conf``. A slow or failing
handler drops calls, so the handlers read a whole compiled document from Redis
and never compile on the request path.

Publishing (and any other control-plane change that alters what is served)
invalidates the current entry. The last-known-good entry is deliberately kept
when the cache is invalidated: if the database or compiler fails, FreeSWITCH is
served the last document that compiled successfully instead of an empty one.
Handlers never write to the database and never invalidate anything.
"""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

from fs_switch.dialplan import NOT_FOUND_DOCUMENT, compile_published_dialplan
from fs_switch.tenants import (
	DEFAULT_TENANT,
	resolve_tenant_from_map,
	tenant_map_from_rows,
	tenant_or_default,
)

SETTINGS_DOCTYPE = "FS Switch Settings"
AGENT_STATUSES = ("Logged Out", "Available", "On Break")

CACHE_ROOT = "fs_switch:xml"
CURRENT_ROOT = f"{CACHE_ROOT}:current"
LAST_KNOWN_GOOD_ROOT = f"{CACHE_ROOT}:last-known-good"
SECRET_HASH_KEY = f"{CACHE_ROOT}:xml-curl-secret-hash"
TENANT_MAP_KEY = f"{CACHE_ROOT}:tenant-map"
CURRENT_TTL = 24 * 60 * 60


def _text(value) -> str:
	return str(value or "").strip()


def _attr(value) -> str:
	from xml.sax.saxutils import quoteattr

	return quoteattr(str(value if value is not None else ""))


class CachedDocument:
	"""One cached document, keyed by kind, tenant and routing label."""

	def __init__(self, store, kind: str, tenant: str = "default", name: str = "default", log=None):
		self.store = store
		self.kind = kind
		self.tenant = tenant or "default"
		self.name = name or "default"
		self.log = log
		self.current_ttl = CURRENT_TTL

	@property
	def current_key(self) -> str:
		return f"{CURRENT_ROOT}:{self.kind}:{self.tenant}:{self.name}"

	@property
	def last_known_good_key(self) -> str:
		return f"{LAST_KNOWN_GOOD_ROOT}:{self.kind}:{self.tenant}:{self.name}"

	def _record(self, message, exc=None):
		if self.log:
			self.log(message, exc)

	def _get(self, key):
		try:
			return self.store.get(key)
		except Exception as exc:
			self._record(f"Could not read {key}: {exc}", exc)
			return None

	def _set(self, key, value, expires_in_sec=None):
		try:
			self.store.set(key, value, expires_in_sec=expires_in_sec)
		except Exception as exc:
			self._record(f"Could not write {key}: {exc}", exc)

	def _delete(self, key):
		try:
			self.store.delete(key)
		except Exception as exc:
			self._record(f"Could not delete {key}: {exc}", exc)

	def serve(self, build) -> str:
		"""Return the cached document, building and caching it on a miss.

		Any build failure falls back to last-known-good, then to the
		FreeSWITCH not-found document. A cache failure is not fatal: the
		handler still returns a freshly built document.
		"""
		cached = self._get(self.current_key)
		if cached:
			return cached

		try:
			xml = build()
		except Exception as exc:
			self._record(f"Could not build {self.kind}: {exc}", exc)
			return self._get(self.last_known_good_key) or NOT_FOUND_DOCUMENT

		xml = xml or NOT_FOUND_DOCUMENT
		self._set(self.current_key, xml, expires_in_sec=self.current_ttl)
		if xml != NOT_FOUND_DOCUMENT:
			# Keep the last document that actually routed something. An
			# intentionally empty dialplan must not erase the safety net.
			self._set(self.last_known_good_key, xml)
		return xml

	def invalidate(self):
		"""Drop the current document. Last-known-good survives on purpose."""
		self._delete(self.current_key)


class FrappeCacheStore:
	"""Adapt Frappe's Redis wrapper to the small store interface above."""

	def __init__(self, frappe_module):
		self.frappe = frappe_module

	def get(self, key):
		return self.frappe.cache.get_value(key)

	def set(self, key, value, expires_in_sec=None):
		self.frappe.cache.set_value(key, value, expires_in_sec=expires_in_sec)

	def delete(self, key):
		self.frappe.cache.delete_value(key)

	def delete_prefix(self, prefix):
		self.frappe.cache.delete_keys(prefix + "*")


def _tenant_map(frappe) -> dict:
	"""Return the cached domain/context -> Tenant map.

	The map is built from enabled FS Tenant rows and the configured default
	Tenant. It is invalidated after a Tenant or Settings change, not on the
	call-setup path. A cache or database failure falls back to the default
	Tenant, matching the single-tenant upgrade path.
	"""
	store = _store(frappe)
	try:
		cached = store.get(TENANT_MAP_KEY)
	except Exception:
		cached = None
	if isinstance(cached, dict) and cached.get("default"):
		return cached

	try:
		settings = frappe.get_single(SETTINGS_DOCTYPE)
		default = tenant_or_default(getattr(settings, "default_tenant", None))
	except Exception:
		default = DEFAULT_TENANT
	try:
		rows = frappe.get_all(
			"FS Tenant",
			filters={"enabled": 1},
			fields=["name", "sip_domain", "default_context", "enabled"],
		)
	except Exception as exc:
		_log(frappe, f"Could not build the tenant map: {exc}", exc)
		rows = []
	mapping = tenant_map_from_rows(rows, default=default)
	try:
		store.set(TENANT_MAP_KEY, mapping, expires_in_sec=CURRENT_TTL)
	except Exception:
		pass
	return mapping


def resolve_tenant(domain=None, context=None) -> str:
	"""Return the Tenant for a FreeSWITCH routing label.

	The mapping is cached in Redis so the call-setup path does not read MariaDB
	for tenant resolution. Unknown labels fall back to the configured default
	Tenant; duplicate labels are rejected when the Tenant is saved.
	"""
	mapping = _tenant_map(_frappe())
	return resolve_tenant_from_map(mapping, domain=domain, context=context)


def secret_hash(value: str) -> str:
	return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def expected_secret_hash() -> str:
	"""Return the xml-curl secret hash, cached so the handler can still auth.

	The hash lives in Redis, not MariaDB. This keeps a handler that is already
	executing alive during a database failure. It does not make a Frappe HTTP
	request independent of MariaDB: Frappe's request middleware can fail before
	the handler runs. If neither store is available the caller fails closed.
	"""
	frappe = _frappe()
	store = _store(frappe)
	try:
		cached = store.get(SECRET_HASH_KEY)
	except Exception:
		cached = None
	if cached:
		return cached

	settings = frappe.get_single(SETTINGS_DOCTYPE)
	secret = settings.get_password("xml_curl_secret", raise_exception=False) or ""
	if not secret:
		return ""
	hashed = secret_hash(secret)
	try:
		store.set(SECRET_HASH_KEY, hashed, expires_in_sec=CURRENT_TTL)
	except Exception:
		pass
	return hashed


def _log(frappe, message, exc=None):
	try:
		frappe.log_error(
			title="FS Switch xml-curl cache",
			message=f"{message}\n\n{exc}" if exc else message,
		)
	except Exception:
		# Logging must never break the call-setup path.
		pass


def _store(frappe) -> FrappeCacheStore:
	return FrappeCacheStore(frappe)


def _document(frappe, kind: str, tenant: str, name: str) -> CachedDocument:
	return CachedDocument(
		_store(frappe),
		kind,
		tenant=tenant,
		name=name,
		log=lambda message, exc=None: _log(frappe, message, exc),
	)


def serve_dialplan(context=None) -> str:
	"""Return the published dialplan document from cache."""
	frappe = _frappe()
	context = _text(context) or "default"
	tenant = resolve_tenant(context=context)
	document = _document(frappe, "dialplan", tenant, context)
	return document.serve(lambda: _build_dialplan(frappe, tenant))


def serve_directory(domain=None) -> str:
	"""Return the directory document for a domain from cache."""
	frappe = _frappe()
	tenant = resolve_tenant(domain=domain)
	document = _document(frappe, "directory", tenant, _text(domain) or "default")
	return document.serve(lambda: _build_directory(frappe, tenant, domain))


def serve_callcenter(context=None) -> str:
	"""Return the global callcenter.conf document from cache.

	FreeSWITCH's configuration request for ``callcenter.conf`` is global rather
	than context-scoped, so one document carries every enabled Tenant's queues
	and agents. Queue and agent names include the Tenant context.
	"""
	frappe = _frappe()
	document = _document(frappe, "callcenter", "all", "all")
	return document.serve(lambda: _build_callcenter(frappe))


def invalidate(kind: str):
	"""Drop every cached document of one kind. Last-known-good is kept."""
	frappe = _frappe()
	try:
		_store(frappe).delete_prefix(f"{CURRENT_ROOT}:{kind}:")
	except Exception as exc:
		_log(frappe, f"Could not invalidate {kind} cache", exc)


def invalidate_dialplan():
	invalidate("dialplan")


def invalidate_directory():
	invalidate("directory")


def invalidate_callcenter():
	invalidate("callcenter")


def invalidate_secret():
	frappe = _frappe()
	try:
		_store(frappe).delete(SECRET_HASH_KEY)
	except Exception as exc:
		_log(frappe, "Could not invalidate the xml-curl secret hash", exc)


def invalidate_tenant_map():
	frappe = _frappe()
	try:
		_store(frappe).delete(TENANT_MAP_KEY)
	except Exception as exc:
		_log(frappe, "Could not invalidate the tenant map cache", exc)


def invalidate_default_tenant():
	"""Backward-compatible name for the tenant map invalidation."""
	invalidate_tenant_map()


def invalidate_all():
	for kind in ("dialplan", "directory", "callcenter"):
		invalidate(kind)
	invalidate_secret()
	invalidate_tenant_map()


def _after_commit(callback):
	frappe = _frappe()
	try:
		frappe.db.after_commit.add(callback)
	except Exception:
		# Older Frappe versions, or no transaction. Invalidate now.
		callback()


def invalidate_after_commit(*kinds: str):
	"""Invalidate once the change is visible to other workers.

	Controllers call this instead of invalidating before commit: a concurrent
	request must not rebuild the cache from the old row and leave it stale.
	"""

	def run():
		for kind in kinds:
			invalidate(kind)

	_after_commit(run)


def invalidate_tenant_after_commit():
	"""Tenant changes alter routing and every document, but not the secret."""

	def run():
		for kind in ("dialplan", "directory", "callcenter"):
			invalidate(kind)
		invalidate_tenant_map()

	_after_commit(run)


def invalidate_all_after_commit():
	_after_commit(invalidate_all)


def _frappe():
	import frappe

	return frappe


def _tenant_field(frappe, tenant: str, field: str):
	"""Read a Tenant field for document builders, with a test-safe fallback."""
	db = getattr(frappe, "db", None)
	if db is None or not hasattr(db, "get_value"):
		return None
	try:
		return db.get_value("FS Tenant", tenant_or_default(tenant), field)
	except Exception:
		return None


def _tenant_context(frappe, tenant: str, settings=None) -> str:
	settings = settings or frappe.get_single(SETTINGS_DOCTYPE)
	value = _tenant_field(frappe, tenant, "default_context")
	return _text(value) or _text(getattr(settings, "default_context", None)) or "default"


def _tenant_domain(frappe, tenant: str, settings=None) -> str:
	settings = settings or frappe.get_single(SETTINGS_DOCTYPE)
	value = _tenant_field(frappe, tenant, "sip_domain")
	return _text(value) or _text(getattr(settings, "sip_domain", None))


def _build_dialplan(frappe, tenant: str) -> str:
	"""Compile only published XML for one tenant into the whole dialplan document."""
	settings = frappe.get_single(SETTINGS_DOCTYPE)
	plans = frappe.get_all(
		"FS Dialplan",
		filters={"enabled": 1, "published_tenant": tenant_or_default(tenant)},
		fields=[
			"name",
			"title",
			"published_context",
			"published_priority",
			"published_xml",
			"published_tenant",
			"enabled",
		],
		order_by="published_priority asc, modified asc",
	)
	published = [
		SimpleNamespace(
			name=row.name,
			title=row.title,
			published_context=row.published_context,
			published_priority=row.published_priority,
			published_xml=row.published_xml,
			enabled=row.enabled,
		)
		for row in plans
		if row.published_xml
	]
	return compile_published_dialplan(published, settings)


def _build_directory(frappe, tenant: str, domain: str | None) -> str:
	settings = frappe.get_single(SETTINGS_DOCTYPE)
	tenant_context = _tenant_context(frappe, tenant, settings)
	tenant_caller_id = _tenant_field(frappe, tenant, "outbound_caller_id")
	users = []
	for row in frappe.get_all(
		"FS Extension",
		filters={"enabled": 1, "tenant": tenant_or_default(tenant)},
		fields=["name", "user", "display_name", "extension"],
		order_by="extension asc",
	):
		doc = frappe.get_doc("FS Extension", row.name)
		full_name = row.display_name
		if not full_name and row.user:
			full_name = frappe.db.get_value("User", row.user, "full_name")
		context = doc.context or tenant_context
		users.append(
			f"<user id={_attr(doc.extension)}>"
			"<params>"
			f'<param name="password" value={_attr(doc.get_password("sip_password"))}/>'
			f'<param name="vm-password" value={_attr(doc.extension)}/>'
			"</params>"
			"<variables>"
			f'<variable name="user_context" value={_attr(context)}/>'
			f'<variable name="effective_caller_id_name" value={_attr(full_name or doc.extension)}/>'
			f'<variable name="effective_caller_id_number" value={_attr(doc.caller_id_number or doc.outbound_caller_id or tenant_caller_id or doc.extension)}/>'
			"</variables></user>"
		)

	domain_name = domain or _tenant_domain(frappe, tenant, settings) or "$${domain}"
	return (
		'<document type="freeswitch/xml">'
		f'<section name="directory"><domain name={_attr(domain_name)}>'
		"<params>"
		'<param name="dial-string" value="{^^:sip_invite_domain=${dialed_domain}:presence_id=${dialed_user}@${dialed_domain}}${sofia_contact(*/${dialed_user}@${dialed_domain})}"/>'
		"</params>"
		'<groups><group name="fs_switch"><users>' + "".join(users) + "</users></group></groups>"
		"</domain></section></document>"
	)


def _build_callcenter(frappe, tenant: str | None = None) -> str:
	settings = frappe.get_single(SETTINGS_DOCTYPE)
	if tenant:
		tenants = [(tenant_or_default(tenant), _tenant_context(frappe, tenant, settings))]
	else:
		rows = frappe.get_all(
			"FS Tenant",
			filters={"enabled": 1},
			fields=["name", "default_context"],
			order_by="name asc",
		)
		tenants = [
			(
				row.name,
				_text(getattr(row, "default_context", None))
				or _text(getattr(settings, "default_context", None))
				or "default",
			)
			for row in rows
			if getattr(row, "name", None)
		]
		if not tenants:
			tenants = [
				(
					tenant_or_default(getattr(settings, "default_tenant", None)),
					_text(getattr(settings, "default_context", None)) or "default",
				)
			]

	queues, tiers, agents = [], [], []
	for tenant_name, context in tenants:
		domain = _tenant_domain(frappe, tenant_name, settings) or "$${domain}"
		hold = (
			_tenant_field(frappe, tenant_name, "hold_music_file")
			or settings.hold_music_file
			or "local_stream://moh"
		)
		queue_specs = []
		used_links = set()
		for row in frappe.get_all(
			"FS Queue",
			filters={"enabled": 1, "tenant": tenant_name},
			fields=["name"],
			order_by="queue_name asc",
		):
			queue = frappe.get_doc("FS Queue", row.name)
			links = [
				(agent.extension, agent.level or 1, agent.position or 0)
				for agent in queue.agents or []
			]
			if queue.backup_queue:
				backup = frappe.get_doc("FS Queue", queue.backup_queue)
				if tenant_or_default(getattr(backup, "tenant", None)) == tenant_name:
					links += [
						(agent.extension, 2, agent.position or 0)
						for agent in backup.agents or []
						if agent.extension not in {member[0] for member in links}
					]
			if not links:
				continue
			queue_specs.append((queue, links))
			used_links.update(link for link, _, _ in links if link)

		extension_rows = (
			frappe.get_all(
				"FS Extension",
				filters={
					"enabled": 1,
					"tenant": tenant_name,
					"name": ["in", sorted(used_links)],
				},
				fields=["name", "extension", "agent_status"],
				order_by="extension asc",
			)
			if used_links
			else []
		)
		extension_by_name = {row.name: row.extension for row in extension_rows}

		for queue, links in queue_specs:
			members = []
			for link, level, position in links:
				extension = extension_by_name.get(link)
				if extension and extension not in {member[0] for member in members}:
					members.append((extension, level, position))
			queue_name = f"{queue.queue_name}@{context}"
			queues.append(
				f"<queue name={_attr(queue_name)}>"
				f'<param name="strategy" value={_attr(queue.strategy or "longest-idle-agent")}/>'
				f'<param name="moh-sound" value={_attr(queue.music_on_hold or hold)}/>'
				f'<param name="max-wait-time" value={_attr(int(queue.max_wait_seconds or 180))}/>'
				'<param name="max-wait-time-with-no-agent" value="30"/>'
				'<param name="discard-abandoned-after" value="60"/>'
				'<param name="abandoned-resume-allowed" value="false"/>'
				'<param name="tier-rules-apply" value="false"/>'
				'<param name="tier-rule-no-agent-no-wait" value="true"/>'
				"</queue>"
			)
			for extension, level, position in members:
				tiers.append(
					f'<tier agent={_attr(f"{extension}@{context}")} '
					f'queue={_attr(queue_name)} level="{int(level)}" position="{int(position)}"/>'
				)

		for row in extension_rows:
			status = row.agent_status if row.agent_status in AGENT_STATUSES else "Logged Out"
			agents.append(
				f'<agent name={_attr(f"{row.extension}@{context}")} type="callback" '
				f'contact={_attr(f"[leg_timeout=30]user/{row.extension}@{domain}")} '
				f'status={_attr(status)} max-no-answer="0" wrap-up-time="30" '
				'reject-delay-time="10" busy-delay-time="0" no-answer-delay-time="10"/>'
			)

	return (
		'<document type="freeswitch/xml">'
		'<section name="configuration"><configuration name="callcenter.conf" description="Call center">'
		"<settings></settings>"
		"<queues>" + "".join(queues) + "</queues>"
		"<agents>" + "".join(agents) + "</agents>"
		"<tiers>" + "".join(tiers) + "</tiers>"
		"</configuration></section></document>"
	)
