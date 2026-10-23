import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "fs_switch"))

from fs_switch.dids import did_key, normalize_did  # noqa: E402


class DIDTest(unittest.TestCase):
    def test_normalizes_carrier_format(self):
        self.assertEqual(normalize_did(" +1 (415) 555-0100 "), "+14155550100")
        self.assertEqual(normalize_did("tel:+44 20 7946 0958"), "+442079460958")
        self.assertEqual(normalize_did("1000"), "1000")

    def test_blank_input_stays_blank(self):
        self.assertEqual(normalize_did(""), "")
        self.assertEqual(normalize_did(None), "")

    def test_comparison_key_ignores_plus_and_formatting(self):
        self.assertEqual(did_key("+1 (415) 555-0100"), "14155550100")
        self.assertEqual(did_key("14155550100"), "14155550100")


if __name__ == "__main__":
    unittest.main()
