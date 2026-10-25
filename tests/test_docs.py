"""Documentation sanity checks.

The user guide is plain Markdown rendered by different consumers (GitHub, a
docs site, or an editor preview). Keep relative links and screenshots honest so
a page does not ship with a broken reference.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


class DocumentationTest(unittest.TestCase):
    def test_relative_links_and_screenshots_exist(self):
        missing = []
        for page in sorted(DOCS.rglob("*.md")):
            text = page.read_text(encoding="utf-8")
            for match in LINK.finditer(text):
                target = match.group(1).strip()
                if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                    continue
                if target.startswith("/"):
                    continue
                target = unquote(target.split("#", 1)[0])
                if not (page.parent / target).exists():
                    missing.append(f"{page.relative_to(ROOT)} -> {target}")
        self.assertFalse(missing, "Broken documentation links:\n" + "\n".join(missing))

    def test_every_document_has_a_heading(self):
        missing = []
        for page in sorted(DOCS.rglob("*.md")):
            text = page.read_text(encoding="utf-8")
            if not re.search(r"^# ", text, re.MULTILINE) and not re.search(
                r"^title:\s*\S", text, re.MULTILINE
            ):
                missing.append(str(page.relative_to(ROOT)))
        self.assertFalse(missing, "Documents without a top-level heading:\n" + "\n".join(missing))

    def test_start_here_links_the_user_guide(self):
        index = (DOCS / "README.md").read_text(encoding="utf-8")
        for page in (
            "installation.md",
            "first-steps.md",
            "tenants.md",
            "dids.md",
            "gateways.md",
            "flows.md",
            "live-operations.md",
            "settings.md",
            "recipes.md",
            "troubleshooting.md",
            "roadmap.md",
            "limitations.md",
        ):
            self.assertIn(f"]({page})", index, f"{page} is not linked from docs/README.md")


if __name__ == "__main__":
    unittest.main()
