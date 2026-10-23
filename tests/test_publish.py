import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "fs_switch"))

from fs_switch.dialplan import DialplanError  # noqa: E402
from fs_switch.publish import (  # noqa: E402
    next_version,
    publish_flow,
    published_status,
    rollback_flow,
)


def raw_graph():
    return json.dumps(
        {
            "nodes": [
                {"id": "answer", "data": {"application": "answer"}},
                {"id": "bye", "data": {"application": "hangup"}},
            ],
            "edges": [{"id": "e1", "source": "answer", "target": "bye"}],
        }
    )


class FakeDoc:
    def __init__(self):
        self.graph = raw_graph()
        self.graph_format = "raw"
        self.extension_name = "publish_test"
        self.destination_number = "^1000$"
        self.context = "default"
        self.priority = 10
        self.enabled = 1
        self.tenant = "default"
        self.compiled_xml = ""
        self.versions = []
        self.published_version = None
        self.published_on = None
        self.published_by = None
        self.published_xml = ""
        self.published_graph = ""
        self.published_graph_format = ""
        self.published_context = ""
        self.published_tenant = ""
        self.published_priority = 0
        self.flags = SimpleNamespace()

    def append(self, key, value):
        self.__dict__.setdefault(key, []).append(SimpleNamespace(**value))


class PublishTest(unittest.TestCase):
    def test_publish_adds_immutable_version_and_updates_pointer(self):
        doc = FakeDoc()
        version = publish_flow(
            doc,
            note="first",
            published_by="Administrator",
            timestamp="2026-10-23 10:00:00",
        )

        self.assertEqual(version, 1)
        self.assertEqual(doc.published_version, 1)
        self.assertEqual(doc.published_on, "2026-10-23 10:00:00")
        self.assertEqual(doc.published_by, "Administrator")
        self.assertEqual(doc.published_context, "default")
        self.assertEqual(doc.published_priority, 10)
        self.assertEqual(doc.published_tenant, "default")
        self.assertIn('extension name="publish_test"', doc.published_xml)
        self.assertEqual(len(doc.versions), 1)
        self.assertEqual(doc.versions[0].note, "first")
        self.assertEqual(doc.versions[0].tenant, "default")
        self.assertEqual(doc.versions[0].compiled_xml, doc.published_xml)
        self.assertTrue(doc.flags.publishing)

        publish_flow(
            doc,
            note="second",
            published_by="Administrator",
            timestamp="2026-10-23 10:05:00",
        )
        self.assertEqual(doc.published_version, 2)
        self.assertEqual(len(doc.versions), 2)
        self.assertEqual(doc.versions[0].note, "first")
        self.assertEqual(doc.versions[1].note, "second")

    def test_rollback_moves_pointer_without_touching_draft(self):
        doc = FakeDoc()
        publish_flow(doc, note="first", timestamp="2026-10-23 10:00:00")
        first_xml = doc.versions[0].compiled_xml
        doc.graph = json.dumps(
            {
                "nodes": [{"id": "bye", "data": {"application": "hangup"}}],
                "edges": [],
            }
        )
        publish_flow(doc, note="second", timestamp="2026-10-23 10:05:00")
        draft_graph = doc.graph

        version = rollback_flow(doc, 1, timestamp="2026-10-23 10:10:00")

        self.assertEqual(version, 1)
        self.assertEqual(doc.published_version, 1)
        self.assertEqual(doc.published_xml, first_xml)
        self.assertEqual(doc.published_tenant, "default")
        self.assertEqual(doc.published_on, "2026-10-23 10:10:00")
        self.assertEqual(doc.graph, draft_graph)
        self.assertEqual(len(doc.versions), 2)
        self.assertTrue(doc.flags.publishing)

    def test_rollback_rejects_unknown_version(self):
        doc = FakeDoc()
        publish_flow(doc, timestamp="2026-10-23 10:00:00")
        with self.assertRaises(ValueError):
            rollback_flow(doc, 99)

    def test_next_version_uses_highest_existing_version(self):
        doc = FakeDoc()
        doc.versions = [SimpleNamespace(version=1), SimpleNamespace(version=4)]
        self.assertEqual(next_version(doc), 5)

    def test_invalid_draft_is_not_published(self):
        doc = FakeDoc()
        doc.graph = "not json"
        with self.assertRaises(DialplanError):
            publish_flow(doc, timestamp="2026-10-23 10:00:00")
        self.assertEqual(doc.versions, [])
        self.assertIsNone(doc.published_version)

    def test_published_status_tracks_xml_context_and_priority(self):
        doc = FakeDoc()
        self.assertEqual(published_status(doc), "Draft")

        doc.published_on = "2026-10-23 10:00:00"
        doc.compiled_xml = "<extension/>"
        doc.published_xml = "<extension/>"
        doc.context = " default "
        doc.published_context = "default"
        doc.priority = "10"
        doc.published_priority = 10
        self.assertEqual(published_status(doc), "Published")

        doc.compiled_xml = "<extension>changed</extension>"
        self.assertEqual(published_status(doc), "Draft")
        doc.compiled_xml = doc.published_xml
        doc.context = "public"
        self.assertEqual(published_status(doc), "Draft")
        doc.context = "default"
        doc.priority = 20
        self.assertEqual(published_status(doc), "Draft")

    def test_published_status_tracks_tenant(self):
        doc = FakeDoc()
        doc.published_on = "2026-10-23 10:00:00"
        doc.compiled_xml = "<extension/>"
        doc.published_xml = "<extension/>"
        doc.published_context = "default"
        doc.published_priority = 10
        doc.published_tenant = "default"
        self.assertEqual(published_status(doc), "Published")

        doc.tenant = "acme"
        self.assertEqual(published_status(doc), "Draft")


if __name__ == "__main__":
    unittest.main()
