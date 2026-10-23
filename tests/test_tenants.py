import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "fs_switch"))

from fs_switch.tenants import DEFAULT_TENANT, fixed_tenant, tenant_or_default  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
