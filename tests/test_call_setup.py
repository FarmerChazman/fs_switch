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


class RecordingFrappe:
    def __init__(self, default_tenant="default", tenants=None):
        self.calls = []
        self.cache = FakeCache()
        self.default_tenant = default_tenant
        self.tenants = tenants or []

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
        return []

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


if __name__ == "__main__":
    unittest.main()
