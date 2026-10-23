import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1] / "apps" / "fs_switch"
sys.path.insert(0, str(APP))

from fs_switch.dialplan import compile_extension  # noqa: E402
from fs_switch.diff import diff_flow  # noqa: E402


def node(node_id, node_type, data=None):
    return {
        "id": node_id,
        "type": node_type,
        "position": {"x": 0, "y": 0},
        "data": data or {},
    }


def edge(edge_id, source, target, handle=None):
    item = {"id": edge_id, "source": source, "target": target}
    if handle:
        item["sourceHandle"] = handle
    return item


def graph(nodes, edges, entry):
    return {"schema": 1, "entry": entry, "nodes": nodes, "edges": edges}


def linear_graph(prompt="ivr/welcome.wav"):
    return graph(
        [
            node("answer", "answer"),
            node("play", "play", {"prompt": prompt}),
            node("bye", "hangup"),
        ],
        [
            edge("e1", "answer", "play"),
            edge("e2", "play", "bye"),
        ],
        entry="answer",
    )


def raw_graph(application="answer", data=None):
    return graph(
        [
            {
                "id": "answer",
                "type": "fs-node",
                "position": {"x": 0, "y": 0},
                "data": {"label": "Answer", "application": "answer", "data": ""},
            },
            {
                "id": "play",
                "type": "fs-node",
                "position": {"x": 0, "y": 0},
                "data": {
                    "label": "Play",
                    "application": application,
                    "data": data if data is not None else "ivr/welcome.wav",
                },
            },
        ],
        [edge("e1", "answer", "play")],
        entry="answer",
    )


def make_doc(draft, published=None, **overrides):
    draft_json = json.dumps(draft) if isinstance(draft, dict) else draft
    published_json = (
        json.dumps(published) if isinstance(published, dict) else (published or "")
    )
    data = {
        "name": "office",
        "title": "Office",
        "graph_format": "semantic",
        "graph": draft_json,
        "published_graph": published_json,
        "extension_name": "office",
        "destination_number": "^1000$",
        "context": "default",
        "priority": 10,
        "enabled": 1,
        "compiled_xml": "",
        "published_xml": "",
        "published_graph_format": "semantic",
        "published_context": "default",
        "published_priority": 10,
        "published_version": 1,
        "published_on": "2026-10-23 10:00:00",
        "published_by": "Administrator",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def with_xml(doc):
    doc.compiled_xml = compile_extension(doc)
    if doc.published_on:
        published_doc = SimpleNamespace(
            graph=doc.published_graph,
            graph_format=doc.published_graph_format,
            extension_name=doc.extension_name,
            destination_number=doc.destination_number,
            context=doc.published_context,
            enabled=doc.enabled,
        )
        doc.published_xml = compile_extension(published_doc)
    return doc


class FlowDiffTest(unittest.TestCase):
    def test_identical_draft_and_published_have_no_changes(self):
        flow = linear_graph()
        result = diff_flow(with_xml(make_doc(flow, flow)))
        self.assertFalse(result["has_changes"])
        self.assertEqual(result["nodes"]["added"], [])
        self.assertEqual(result["nodes"]["removed"], [])
        self.assertEqual(result["nodes"]["changed"], [])
        self.assertEqual(result["edges"]["added"], [])
        self.assertEqual(result["edges"]["removed"], [])
        self.assertFalse(result["xml"]["changed"])

    def test_changed_node_and_added_node_are_reported(self):
        published = linear_graph(prompt="ivr/old.wav")
        draft = graph(
            [
                node("answer", "answer"),
                node("set", "set", {"variable": "source", "value": "ivr"}),
                node("play", "play", {"prompt": "ivr/new.wav"}),
                node("bye", "hangup"),
            ],
            [
                edge("e1", "answer", "set"),
                edge("e2", "set", "play"),
                edge("e3", "play", "bye"),
            ],
            entry="answer",
        )
        result = diff_flow(with_xml(make_doc(draft, published)))

        self.assertTrue(result["has_changes"])
        self.assertEqual([item["id"] for item in result["nodes"]["added"]], ["set"])
        self.assertEqual(result["nodes"]["removed"], [])
        changed = {item["id"]: item for item in result["nodes"]["changed"]}
        self.assertIn("play", changed)
        fields = {item["field"]: item for item in changed["play"]["changes"]}
        self.assertEqual(fields["prompt"]["draft"], "ivr/new.wav")
        self.assertEqual(fields["prompt"]["published"], "ivr/old.wav")

        added_edges = {
            (item["source"], item["source_handle"], item["target"])
            for item in result["edges"]["added"]
        }
        removed_edges = {
            (item["source"], item["source_handle"], item["target"])
            for item in result["edges"]["removed"]
        }
        self.assertIn(("answer", "next", "set"), added_edges)
        self.assertIn(("set", "next", "play"), added_edges)
        self.assertIn(("answer", "next", "play"), removed_edges)

    def test_removed_node_and_edge_are_reported(self):
        published = linear_graph()
        draft = graph(
            [node("answer", "answer"), node("bye", "hangup")],
            [edge("e1", "answer", "bye")],
            entry="answer",
        )
        result = diff_flow(with_xml(make_doc(draft, published)))
        self.assertEqual([item["id"] for item in result["nodes"]["removed"]], ["play"])
        removed = {
            (item["source"], item["source_handle"], item["target"])
            for item in result["edges"]["removed"]
        }
        self.assertIn(("answer", "next", "play"), removed)
        self.assertIn(("play", "next", "bye"), removed)

    def test_edge_ids_and_positions_are_not_changes(self):
        published = linear_graph()
        draft = linear_graph()
        draft["edges"] = [
            edge("new-a", "answer", "play"),
            edge("new-b", "play", "bye"),
        ]
        for item in draft["nodes"]:
            item["position"] = {"x": 999, "y": 999}
        result = diff_flow(with_xml(make_doc(draft, published)))
        self.assertFalse(result["has_changes"])

    def test_settings_changes_are_reported(self):
        flow = linear_graph()
        result = diff_flow(
            with_xml(
                make_doc(
                    flow,
                    flow,
                    context="sales",
                    priority=20,
                    published_context="default",
                    published_priority=10,
                )
            )
        )
        settings = {item["field"]: item for item in result["settings"]}
        self.assertTrue(settings["context"]["changed"])
        self.assertEqual(settings["context"]["draft"], "sales")
        self.assertEqual(settings["context"]["published"], "default")
        self.assertTrue(settings["priority"]["changed"])
        self.assertEqual(settings["priority"]["draft"], 20)

    def test_entry_change_is_reported(self):
        published = raw_graph()
        draft = raw_graph()
        draft["entry"] = "play"
        result = diff_flow(
            with_xml(
                make_doc(
                    draft,
                    published,
                    graph_format="raw",
                    published_graph_format="raw",
                )
            )
        )
        self.assertTrue(result["entry"]["changed"])
        self.assertEqual(result["entry"]["draft"], "play")
        self.assertEqual(result["entry"]["published"], "answer")

    def test_raw_flow_changes_are_reported(self):
        published = raw_graph(application="answer", data="")
        draft = raw_graph(application="playback", data="ivr/welcome.wav")
        result = diff_flow(
            with_xml(
                make_doc(
                    draft,
                    published,
                    graph_format="raw",
                    published_graph_format="raw",
                )
            )
        )
        changed = {item["id"]: item for item in result["nodes"]["changed"]}
        self.assertIn("play", changed)
        fields = {item["field"]: item for item in changed["play"]["changes"]}
        self.assertEqual(fields["application"]["draft"], "playback")
        self.assertEqual(fields["data"]["draft"], "ivr/welcome.wav")
        self.assertIn("playback", result["xml"]["diff"])

    def test_never_published_reports_the_draft_as_all_added(self):
        flow = linear_graph()
        result = diff_flow(
            make_doc(
                flow,
                None,
                published_graph="",
                published_graph_format="",
                published_context="",
                published_priority=0,
                published_version=0,
                published_on=None,
                published_by="",
            )
        )
        self.assertTrue(result["never_published"])
        self.assertTrue(result["has_changes"])
        self.assertEqual(
            [item["id"] for item in result["nodes"]["added"]],
            ["answer", "play", "bye"],
        )
        self.assertEqual(result["xml"]["diff"], "")

    def test_invalid_draft_graph_is_reported_without_hiding_settings(self):
        published = linear_graph()
        result = diff_flow(
            make_doc(
                "{not-json",
                published,
                context="sales",
            )
        )
        self.assertTrue(result["has_changes"])
        self.assertTrue(result["errors"])
        self.assertIn("not valid JSON", " ".join(result["errors"]))
        settings = {item["field"]: item for item in result["settings"]}
        self.assertTrue(settings["context"]["changed"])

    def test_xml_diff_contains_published_and_draft_headers(self):
        published = linear_graph(prompt="ivr/old.wav")
        draft = linear_graph(prompt="ivr/new.wav")
        result = diff_flow(with_xml(make_doc(draft, published)))
        self.assertTrue(result["xml"]["changed"])
        self.assertIn("--- Published", result["xml"]["diff"])
        self.assertIn("+++ Draft", result["xml"]["diff"])
        self.assertIn("ivr/old.wav", result["xml"]["diff"])
        self.assertIn("ivr/new.wav", result["xml"]["diff"])


if __name__ == "__main__":
    unittest.main()
