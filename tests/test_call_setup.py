import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1] / "apps" / "fs_switch"
sys.path.insert(0, str(APP))

from fs_switch import call_setup  # noqa: E402
from fs_switch.call_setup import (  # noqa: E402
    CURRENT_ROOT,
    LAST_KNOWN_GOOD_ROOT,
    NOT_FOUND_DOCUMENT,
    SECRET_HASH_KEY,
    CachedDocument,
    _build_callcenter,
    _build_dialplan,
    _build_directory,
    expected_secret_hash,
    invalidate_all,
    invalidate_dialplan,
    resolve_tenant,
    secret_hash,
    serve_dialplan,
)


class FakeCache:
    def __init__(self):
        self.values = {}

    def get_value(self, key):
        return self.values.get(key)

    def set_value(self, key, value, expires_in_sec=None):
        self.values[key] = value

    def delete_value(self, key):
        self.values.pop(key, None)

    def delete_keys(self, pattern):
        prefix = pattern.rstrip("*")
        for key in [key for key in self.values if key.startswith(prefix)]:
            self.values.pop(key)


class FakeFrappe:
    def __init__(self, plans=None, secret="s3cret"):
        self.cache = FakeCache()
        self.plans = plans or []
        self.errors = []
        self.get_all_error = None
        self.get_single_error = None
        self.secret = secret

    def get_single(self, doctype):
        if self.get_single_error:
            raise self.get_single_error
        return SimpleNamespace(
            default_context="default",
            main_did="",
            allow_internal_calls=0,
            get_password=lambda field, raise_exception=False: self.secret,
        )

    def get_all(self, doctype, **kwargs):
        if self.get_all_error:
            raise self.get_all_error
        return self.plans

    def log_error(self, title=None, message=None):
        self.errors.append((title, message))


class MemoryStore:
    def __init__(self):
        self.values = {}
        self.writes = []

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, expires_in_sec=None):
        self.values[key] = value
        self.writes.append((key, value, expires_in_sec))

    def delete(self, key):
        self.values.pop(key, None)

    def delete_prefix(self, prefix):
        for key in [key for key in self.values if key.startswith(prefix)]:
            self.values.pop(key)


class BrokenStore(MemoryStore):
    def get(self, key):
        raise ConnectionError("redis down")

    def set(self, key, value, expires_in_sec=None):
        raise ConnectionError("redis down")


class CallSetupCacheTest(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.logs = []
        self.document = CachedDocument(
            self.store,
            "dialplan",
            tenant="acme",
            name="default",
            log=lambda message, exc=None: self.logs.append(message),
        )

    def test_cache_miss_builds_and_caches_current_and_last_known_good(self):
        calls = []

        def build():
            calls.append(1)
            return "<published/>"

        self.assertEqual(self.document.serve(build), "<published/>")
        self.assertEqual(self.document.serve(build), "<published/>")
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.store.values[self.document.current_key], "<published/>")
        self.assertEqual(self.store.values[self.document.last_known_good_key], "<published/>")

    def test_keys_are_scoped_to_tenant_and_context(self):
        other = CachedDocument(self.store, "dialplan", tenant="acme", name="sales")
        self.assertNotEqual(self.document.current_key, other.current_key)
        self.assertIn(f"{CURRENT_ROOT}:dialplan:acme:default", self.document.current_key)
        self.assertIn(
            f"{LAST_KNOWN_GOOD_ROOT}:dialplan:acme:default",
            self.document.last_known_good_key,
        )

    def test_build_failure_serves_last_known_good_without_overwriting_it(self):
        self.document.serve(lambda: "<good/>")
        self.document.invalidate()

        def broken():
            raise RuntimeError("database down")

        self.assertEqual(self.document.serve(broken), "<good/>")
        self.assertEqual(self.store.values[self.document.last_known_good_key], "<good/>")
        self.assertEqual(len(self.logs), 1)

    def test_build_failure_without_last_known_good_returns_not_found(self):
        def broken():
            raise RuntimeError("database down")

        self.assertEqual(self.document.serve(broken), NOT_FOUND_DOCUMENT)

    def test_empty_build_is_cached_as_not_found(self):
        self.assertEqual(self.document.serve(lambda: ""), NOT_FOUND_DOCUMENT)
        self.assertEqual(self.store.values[self.document.current_key], NOT_FOUND_DOCUMENT)
        self.assertNotIn(self.document.last_known_good_key, self.store.values)

    def test_empty_build_does_not_erase_last_known_good(self):
        self.document.serve(lambda: "<good/>")
        self.document.invalidate()
        self.assertEqual(self.document.serve(lambda: ""), NOT_FOUND_DOCUMENT)
        self.assertEqual(self.store.values[self.document.last_known_good_key], "<good/>")

    def test_invalidate_drops_current_but_keeps_last_known_good(self):
        self.document.serve(lambda: "<good/>")
        self.document.invalidate()
        self.assertNotIn(self.document.current_key, self.store.values)
        self.assertIn(self.document.last_known_good_key, self.store.values)

        def broken():
            raise RuntimeError("database down")

        self.assertEqual(self.document.serve(broken), "<good/>")

    def test_cache_failure_never_breaks_the_handler(self):
        document = CachedDocument(BrokenStore(), "dialplan", tenant="acme", name="default")
        self.assertEqual(document.serve(lambda: "<published/>"), "<published/>")

    def test_not_found_document_uses_freeswitch_result_shape(self):
        self.assertEqual(
            NOT_FOUND_DOCUMENT,
            '<document type="freeswitch/xml"><section name="result">'
            '<result status="not found"/></section></document>',
        )


class DialplanHandlerTest(unittest.TestCase):
    def setUp(self):
        self.published = SimpleNamespace(
            name="Inbound",
            title="Inbound",
            enabled=1,
            published_context="default",
            published_priority=10,
            published_xml=(
                '    <extension name="inbound">'
                '<condition field="destination_number" expression="^1000$"/>'
                "</extension>"
            ),
        )
        self.fake = FakeFrappe([self.published])
        self.original_frappe = call_setup._frappe
        call_setup._frappe = lambda: self.fake

    def tearDown(self):
        call_setup._frappe = self.original_frappe

    def test_handler_serves_published_xml_from_cache(self):
        first = serve_dialplan("default")
        self.assertIn('extension name="inbound"', first)
        self.fake.plans = []
        self.assertEqual(serve_dialplan("default"), first)

    def test_handler_serves_last_known_good_when_the_database_fails(self):
        first = serve_dialplan("default")
        invalidate_dialplan()
        self.fake.get_all_error = RuntimeError("database down")
        self.assertEqual(serve_dialplan("default"), first)
        self.assertTrue(self.fake.errors)

    def test_handler_returns_not_found_without_published_flows(self):
        self.fake.plans = []
        self.assertEqual(serve_dialplan("default"), NOT_FOUND_DOCUMENT)

    def test_invalidation_keeps_last_known_good(self):
        first = serve_dialplan("default")
        invalidate_dialplan()
        self.assertNotIn(
            f"{CURRENT_ROOT}:dialplan:default:default",
            self.fake.cache.values,
        )
        self.assertIn(
            f"{LAST_KNOWN_GOOD_ROOT}:dialplan:default:default",
            self.fake.cache.values,
        )
        self.fake.get_all_error = RuntimeError("database down")
        self.assertEqual(serve_dialplan("default"), first)

    def test_secret_hash_is_cached_for_a_database_outage(self):
        self.assertEqual(expected_secret_hash(), secret_hash("s3cret"))
        self.fake.get_single_error = RuntimeError("database down")
        self.assertEqual(expected_secret_hash(), secret_hash("s3cret"))

    def test_missing_secret_is_not_cached(self):
        self.fake.secret = ""
        self.assertEqual(expected_secret_hash(), "")
        self.assertFalse(self.fake.cache.values)

    def test_invalidate_all_clears_the_cached_secret_hash(self):
        expected_secret_hash()
        self.assertIn(SECRET_HASH_KEY, self.fake.cache.values)
        invalidate_all()
        self.assertNotIn(SECRET_HASH_KEY, self.fake.cache.values)


class PublicFrappe:
    """Minimal Frappe surface for the shared public dialplan handler."""

    def __init__(self, tenants=None, dids=None, flows=None, main_did="1000"):
        self.cache = FakeCache()
        self.tenants = tenants or []
        self.dids = dids or []
        self.flows = flows or []
        self.main_did = main_did
        self.errors = []

    def get_single(self, doctype):
        return SimpleNamespace(
            default_context="default",
            default_tenant="default",
            main_did=self.main_did,
            allow_internal_calls=0,
        )

    def get_all(self, doctype, **kwargs):
        return {
            "FS Tenant": self.tenants,
            "FS DID": self.dids,
            "FS Dialplan": self.flows,
        }.get(doctype, [])

    def log_error(self, title=None, message=None):
        self.errors.append((title, message))


class PublicDialplanHandlerTest(unittest.TestCase):
    def setUp(self):
        self.original_frappe = call_setup._frappe

    def tearDown(self):
        call_setup._frappe = self.original_frappe

    def _flow(self, name, tenant, context, published=True):
        return SimpleNamespace(
            name=name,
            title=name,
            tenant=tenant,
            enabled=1,
            published_tenant=tenant if published else "",
            published_context=context if published else "",
            published_priority=10,
            published_xml='<extension name="%s"/>' % name if published else "",
        )

    def test_public_context_routes_dids_for_all_tenants(self):
        self.fake = PublicFrappe(
            tenants=[
                SimpleNamespace(name="accept-a", enabled=1),
                SimpleNamespace(name="accept-b", enabled=1),
            ],
            dids=[
                SimpleNamespace(number="+14155550101", tenant="accept-a", enabled=1, flow="accept-a::Flow A"),
                SimpleNamespace(number="14155550102", tenant="accept-b", enabled=1, flow="accept-b::Flow B"),
            ],
            flows=[
                self._flow("accept-a::Flow A", "accept-a", "accept_a"),
                self._flow("accept-b::Flow B", "accept-b", "accept_b"),
            ],
        )
        call_setup._frappe = lambda: self.fake

        xml = serve_dialplan("public")

        self.assertIn('<context name="public">', xml)
        self.assertIn("+14155550101 XML accept_a", xml)
        self.assertIn("14155550102 XML accept_b", xml)
        self.assertNotIn('<context name="accept_a">', xml)
        self.assertIn("fs_switch:xml:current:dialplan:all:public", self.fake.cache.values)
        self.assertIn("1000 XML default", xml)

    def test_public_context_uses_the_tenant_main_did_for_an_unassigned_did(self):
        self.fake = PublicFrappe(
            tenants=[
                SimpleNamespace(
                    name="accept-a",
                    enabled=1,
                    main_did="+14155550100",
                    default_context="accept_a",
                )
            ],
            dids=[
                SimpleNamespace(
                    number="+14155550109",
                    tenant="accept-a",
                    enabled=1,
                    flow="",
                )
            ],
            flows=[],
            main_did="",
        )
        call_setup._frappe = lambda: self.fake

        xml = serve_dialplan("public")

        self.assertIn("+14155550100 XML accept_a", xml)
        self.assertIn('expression="^\\+?14155550109$"', xml)

    def test_public_context_skips_disabled_or_unpublished_routes(self):
        self.fake = PublicFrappe(
            tenants=[
                SimpleNamespace(name="accept-a", enabled=1),
                SimpleNamespace(name="old", enabled=0),
            ],
            dids=[
                SimpleNamespace(number="+14155550101", tenant="accept-a", enabled=1, flow="accept-a::Draft"),
                SimpleNamespace(number="+14155550102", tenant="accept-a", enabled=1, flow="accept-a::Published"),
                SimpleNamespace(number="+14155550103", tenant="old", enabled=1, flow="old::Published"),
                SimpleNamespace(number="+14155550104", tenant="accept-a", enabled=1, flow="accept-a::Other"),
                SimpleNamespace(number="+14155550105", tenant="accept-a", enabled=1, flow="accept-a::Public"),
                SimpleNamespace(number="+14155550106", tenant="accept-a", enabled=0, flow="accept-a::Published"),
            ],
            flows=[
                self._flow("accept-a::Draft", "accept-a", "accept_a", published=False),
                self._flow("accept-a::Published", "accept-a", "accept_a"),
                self._flow("old::Published", "old", "old"),
                self._flow("accept-a::Other", "accept-b", "accept_b"),
                self._flow("accept-a::Public", "accept-a", "public"),
            ],
            main_did="",
        )
        call_setup._frappe = lambda: self.fake

        xml = serve_dialplan("public")

        self.assertIn("+14155550102 XML accept_a", xml)
        self.assertNotIn("+14155550101", xml)
        self.assertNotIn("+14155550103", xml)
        self.assertNotIn("+14155550104", xml)
        self.assertNotIn("+14155550105", xml)
        self.assertNotIn("+14155550106", xml)


class RecordingFrappe:
    def __init__(self, default_tenant="default", tenants=None):
        self.calls = []
        self.cache = FakeCache()
        self.default_tenant = default_tenant
        self.tenants = tenants or []
        self.queues = {}
        self.queue_docs = {}
        self.extensions = {}

    def get_single(self, doctype):
        return SimpleNamespace(
            default_context="default",
            default_tenant=self.default_tenant,
            sip_domain="localhost",
            hold_music_file="local_stream://moh",
            main_did="",
            allow_internal_calls=1,
        )

    def get_all(self, doctype, **kwargs):
        self.calls.append((doctype, kwargs))
        if doctype == "FS Tenant":
            return self.tenants
        if doctype == "FS Queue":
            tenant = kwargs.get("filters", {}).get("tenant")
            return [SimpleNamespace(name=name) for name in self.queues.get(tenant, [])]
        if doctype == "FS Extension":
            tenant = kwargs.get("filters", {}).get("tenant")
            names = kwargs.get("filters", {}).get("name", ["in", []])[1]
            return [
                row
                for row in self.extensions.get(tenant, [])
                if not names or row.name in names
            ]
        return []

    def get_doc(self, doctype, name):
        self.calls.append((doctype, {"name": name}))
        if doctype == "FS Queue":
            return self.queue_docs[name]
        raise KeyError(name)

    def log_error(self, title=None, message=None):
        pass


class TenantScopeTest(unittest.TestCase):
    def setUp(self):
        self.fake = RecordingFrappe()
        self.original_frappe = call_setup._frappe
        call_setup._frappe = lambda: self.fake

    def tearDown(self):
        call_setup._frappe = self.original_frappe

    def test_resolve_tenant_falls_back_to_the_default(self):
        self.assertEqual(resolve_tenant(domain="acme.example", context="sales"), "default")

    def test_resolve_tenant_uses_domain_and_context_mappings(self):
        self.fake.tenants = [
            SimpleNamespace(
                name="default",
                enabled=1,
                sip_domain="localhost",
                default_context="default",
            ),
            SimpleNamespace(
                name="acme",
                enabled=1,
                sip_domain="acme.example",
                default_context="sales",
            ),
        ]
        self.assertEqual(resolve_tenant(domain="ACME.EXAMPLE:5060"), "acme")
        self.assertEqual(resolve_tenant(context="SALES"), "acme")
        self.assertEqual(resolve_tenant(domain="unknown.example"), "default")

    def test_tenant_map_cache_is_invalidated(self):
        self.fake.tenants = [
            SimpleNamespace(
                name="acme",
                enabled=1,
                sip_domain="acme.example",
                default_context="acme",
            )
        ]
        self.assertEqual(resolve_tenant(domain="acme.example"), "acme")
        self.fake.tenants = [
            SimpleNamespace(
                name="beta",
                enabled=1,
                sip_domain="beta.example",
                default_context="beta",
            )
        ]
        self.assertEqual(resolve_tenant(domain="acme.example"), "acme")
        call_setup.invalidate_tenant_map()
        self.assertEqual(resolve_tenant(domain="acme.example"), "default")
        self.assertEqual(resolve_tenant(domain="beta.example"), "beta")

    def test_resolve_tenant_uses_the_configured_default_and_caches_it(self):
        self.fake.default_tenant = "acme"
        self.assertEqual(resolve_tenant(), "acme")
        self.fake.default_tenant = "other"
        self.assertEqual(resolve_tenant(), "acme")

    def test_dialplan_builder_filters_by_published_tenant(self):
        _build_dialplan(self.fake, "acme")
        self.assertEqual(self.fake.calls[0][0], "FS Dialplan")
        self.assertEqual(
            self.fake.calls[0][1]["filters"], {"enabled": 1, "published_tenant": "acme"}
        )

    def test_directory_builder_filters_by_tenant(self):
        _build_directory(self.fake, "acme", "acme.example")
        self.assertEqual(self.fake.calls[0][0], "FS Extension")
        self.assertEqual(self.fake.calls[0][1]["filters"], {"enabled": 1, "tenant": "acme"})

    def test_callcenter_builder_filters_by_tenant(self):
        _build_callcenter(self.fake, "acme")
        self.assertEqual(self.fake.calls[0][0], "FS Queue")
        self.assertEqual(self.fake.calls[0][1]["filters"], {"enabled": 1, "tenant": "acme"})

    def test_callcenter_builder_includes_every_enabled_tenant_by_default(self):
        self.fake.tenants = [
            SimpleNamespace(name="default", default_context="default"),
            SimpleNamespace(name="acme", default_context="sales"),
        ]
        _build_callcenter(self.fake)
        self.assertEqual(self.fake.calls[0][0], "FS Tenant")
        queue_filters = [
            call[1]["filters"]
            for call in self.fake.calls
            if call[0] == "FS Queue" and "filters" in call[1]
        ]
        self.assertEqual(
            queue_filters,
            [
                {"enabled": 1, "tenant": "default"},
                {"enabled": 1, "tenant": "acme"},
            ],
        )

    def test_callcenter_document_contains_queues_and_agents_for_all_tenants(self):
        self.fake.tenants = [
            SimpleNamespace(name="default", default_context="default"),
            SimpleNamespace(name="acme", default_context="sales"),
        ]
        self.fake.queues = {"default": ["support"], "acme": ["sales"]}
        self.fake.queue_docs = {
            "support": SimpleNamespace(
                queue_name="support",
                backup_queue="",
                agents=[SimpleNamespace(extension="1001", level=1, position=1)],
                strategy="longest-idle-agent",
                music_on_hold="",
                max_wait_seconds=180,
            ),
            "sales": SimpleNamespace(
                queue_name="sales",
                backup_queue="",
                agents=[SimpleNamespace(extension="2001", level=1, position=1)],
                strategy="longest-idle-agent",
                music_on_hold="",
                max_wait_seconds=180,
            ),
        }
        self.fake.extensions = {
            "default": [
                SimpleNamespace(name="1001", extension="1001", agent_status="Available")
            ],
            "acme": [
                SimpleNamespace(name="2001", extension="2001", agent_status="On Break")
            ],
        }

        xml = _build_callcenter(self.fake)

        self.assertIn('<queue name="support@default">', xml)
        self.assertIn('<queue name="sales@sales">', xml)
        self.assertIn('<agent name="1001@default"', xml)
        self.assertIn('<agent name="2001@sales"', xml)
        self.assertIn('<tier agent="1001@default" queue="support@default"', xml)
        self.assertIn('<tier agent="2001@sales" queue="sales@sales"', xml)

    def test_callcenter_resolves_tenant_scoped_extension_links(self):
        self.fake.tenants = [
            SimpleNamespace(name="default", default_context="default"),
            SimpleNamespace(name="acme", default_context="sales"),
        ]
        self.fake.queues = {"default": [], "acme": ["acme::support"]}
        self.fake.queue_docs = {
            "acme::support": SimpleNamespace(
                queue_name="support",
                backup_queue="",
                agents=[SimpleNamespace(extension="acme::1001", level=1, position=1)],
                strategy="longest-idle-agent",
                music_on_hold="",
                max_wait_seconds=180,
            )
        }
        self.fake.extensions = {
            "acme": [
                SimpleNamespace(
                    name="acme::1001",
                    extension="1001",
                    agent_status="Available",
                )
            ]
        }

        xml = _build_callcenter(self.fake)

        self.assertIn('<agent name="1001@sales"', xml)
        self.assertIn('<tier agent="1001@sales" queue="support@sales"', xml)
        self.assertNotIn("acme::1001@sales", xml)


if __name__ == "__main__":
    unittest.main()
