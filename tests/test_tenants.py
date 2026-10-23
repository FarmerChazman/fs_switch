import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "fs_switch"))

from fs_switch.tenants import (  # noqa: E402
    DEFAULT_TENANT,
    fixed_tenant,
    normalize_context,
    normalize_domain,
    resolve_tenant_from_map,
    tenant_map_from_rows,
    tenant_or_default,
    tenant_scoped_name,
)


class FakeDoc:
    def __init__(self, tenant=None, before=None):
        self.tenant = tenant
        self._before = before

    def get_doc_before_save(self):
        return self._before


class TenantTest(unittest.TestCase):
    def test_tenant_or_default_normalizes_blank_values(self):
        self.assertEqual(tenant_or_default("  "), DEFAULT_TENANT)
        self.assertEqual(tenant_or_default(None), DEFAULT_TENANT)
        self.assertEqual(tenant_or_default(" acme "), "acme")

    def test_new_document_uses_its_tenant_or_the_default(self):
        self.assertEqual(fixed_tenant(FakeDoc("acme")), "acme")
        self.assertEqual(fixed_tenant(FakeDoc("")), DEFAULT_TENANT)

    def test_existing_document_keeps_its_original_tenant(self):
        doc = FakeDoc("acme", before=SimpleNamespace(tenant="default"))
        self.assertEqual(fixed_tenant(doc), "default")

    def test_existing_document_without_a_tenant_uses_the_default(self):
        doc = FakeDoc("acme", before=SimpleNamespace(tenant=""))
        self.assertEqual(fixed_tenant(doc), DEFAULT_TENANT)


class TenantScopedNameTest(unittest.TestCase):
    def test_natural_key_is_namespaced_by_tenant(self):
        self.assertEqual(tenant_scoped_name(" Accept-A ", " 7101 "), "accept-a::7101")
        self.assertEqual(tenant_scoped_name("", "1001"), "default::1001")
        self.assertEqual(tenant_scoped_name("acme", "Sales"), "acme::Sales")

    def test_blank_key_still_produces_a_stable_name(self):
        self.assertEqual(tenant_scoped_name("acme", ""), "acme::untitled")

    def test_long_keys_are_shortened_with_a_hash_suffix(self):
        name = tenant_scoped_name("acme", "x" * 300)
        self.assertLessEqual(len(name), 140)
        self.assertTrue(name.startswith("acme::"))
        self.assertIn("#", name)
        self.assertEqual(name, tenant_scoped_name("acme", "x" * 300))


class TenantMappingTest(unittest.TestCase):
    def test_domains_are_lowercase_without_a_port_or_trailing_dot(self):
        self.assertEqual(normalize_domain(" Acme.Example.COM. "), "acme.example.com")
        self.assertEqual(normalize_domain("acme.example.com:5060"), "acme.example.com")
        self.assertEqual(normalize_domain("[2001:db8::1]:5060"), "[2001:db8::1]:5060")
        self.assertEqual(normalize_domain(""), "")

    def test_contexts_are_lowercase_and_trimmed(self):
        self.assertEqual(normalize_context(" Sales "), "sales")
        self.assertEqual(normalize_context(None), "")

    def test_map_contains_enabled_domains_and_contexts(self):
        mapping = tenant_map_from_rows(
            [
                {"name": "default", "enabled": 1, "sip_domain": "localhost", "default_context": "default"},
                {"name": "acme", "enabled": 1, "sip_domain": "acme.example.com", "default_context": "acme"},
                {"name": "old", "enabled": 0, "sip_domain": "old.example.com", "default_context": "old"},
            ],
            default="default",
        )
        self.assertEqual(mapping["default"], "default")
        self.assertEqual(mapping["domains"]["acme.example.com"], "acme")
        self.assertEqual(mapping["contexts"]["acme"], "acme")
        self.assertNotIn("old.example.com", mapping["domains"])
        self.assertNotIn("old", mapping["contexts"])

    def test_first_duplicate_label_wins(self):
        mapping = tenant_map_from_rows(
            [
                {"name": "first", "enabled": 1, "sip_domain": "shared.example", "default_context": "shared"},
                {"name": "second", "enabled": 1, "sip_domain": "shared.example", "default_context": "shared"},
            ],
            default="default",
        )
        self.assertEqual(mapping["domains"]["shared.example"], "first")
        self.assertEqual(mapping["contexts"]["shared"], "first")

    def test_context_wins_when_domain_and_context_disagree(self):
        mapping = {
            "default": "default",
            "domains": {"acme.example": "acme"},
            "contexts": {"sales": "sales"},
        }
        self.assertEqual(
            resolve_tenant_from_map(mapping, domain="acme.example", context="sales"),
            "sales",
        )

    def test_domain_resolves_and_unknown_labels_fall_back(self):
        mapping = {
            "default": "fallback",
            "domains": {"acme.example": "acme"},
            "contexts": {"sales": "sales"},
        }
        self.assertEqual(resolve_tenant_from_map(mapping, domain="ACME.EXAMPLE:5060"), "acme")
        self.assertEqual(resolve_tenant_from_map(mapping, context="unknown"), "fallback")
        self.assertEqual(resolve_tenant_from_map(None, domain="unknown"), DEFAULT_TENANT)


if __name__ == "__main__":
    unittest.main()
