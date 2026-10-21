import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1] / "apps" / "fs_switch"
sys.path.insert(0, str(APP))

from fs_switch.dialplan import (  # noqa: E402
    DialplanError,
    compile_dialplan,
    compile_extension,
    inbound_pattern,
    ordered_nodes,
)


def graph(nodes, edges):
    return json.dumps({"nodes": nodes, "edges": edges})


def node(node_id, application, data="", label=None):
    return {
        "id": node_id,
        "type": "fs-node",
        "position": {"x": 0, "y": 0},
        "data": {"label": label or application, "application": application, "data": data},
    }


class DialplanTest(unittest.TestCase):
    def test_edge_order_wins_over_array_order(self):
        nodes = [node("hangup", "hangup"), node("answer", "answer")]
        edges = [{"id": "e1", "source": "answer", "target": "hangup"}]
        ordered = ordered_nodes(nodes, edges)
        self.assertEqual([item["id"] for item in ordered], ["answer", "hangup"])

    def test_compile_linear_extension(self):
        plan = SimpleNamespace(
            graph=graph(
                [node("answer", "answer"), node("play", "playback", "ivr/welcome.wav"), node("bye", "hangup")],
                [
                    {"id": "e1", "source": "answer", "target": "play"},
                    {"id": "e2", "source": "play", "target": "bye"},
                ],
            ),
            extension_name="office_ivr",
            destination_number="^1000$",
        )
        xml = compile_extension(plan)
        self.assertIn('extension name="office_ivr"', xml)
        self.assertIn('expression="^1000$"', xml)
        self.assertLess(xml.index('application="answer"'), xml.index('application="playback"'))
        self.assertLess(xml.index('application="playback"'), xml.index('application="hangup"'))

    def test_cycle_is_rejected(self):
        nodes = [node("a", "answer"), node("b", "hangup")]
        edges = [
            {"id": "e1", "source": "a", "target": "b"},
            {"id": "e2", "source": "b", "target": "a"},
        ]
        with self.assertRaises(DialplanError):
            ordered_nodes(nodes, edges)

    def test_missing_application_is_rejected(self):
        plan = SimpleNamespace(
            graph=graph([{"id": "x", "data": {"label": "broken"}}], []),
            extension_name="broken",
            destination_number=".*",
        )
        with self.assertRaises(DialplanError):
            compile_extension(plan)

    def test_inbound_pattern_accepts_optional_plus(self):
        self.assertEqual(inbound_pattern("+61 2 5550 1000"), r"^\+?61255501000$")
        self.assertEqual(inbound_pattern("1000"), r"^\+?1000$")
        self.assertEqual(inbound_pattern(""), "")

    def test_compile_dialplan_merges_internal_extension_into_default_context(self):
        plan = SimpleNamespace(
            graph=graph([node("answer", "answer")], []),
            extension_name="inbound",
            destination_number="^1000$",
            context="default",
            priority=10,
            enabled=1,
            title="Inbound",
        )
        settings = SimpleNamespace(
            default_context="default",
            main_did="1000",
            allow_internal_calls=1,
        )
        xml = compile_dialplan([plan], settings)
        self.assertEqual(xml.count('<context name="default">'), 1)
        self.assertIn('extension name="inbound"', xml)
        self.assertIn('extension name="fs_switch_internal"', xml)
        self.assertIn('context name="public"', xml)
        self.assertIn('application="transfer"', xml)


if __name__ == "__main__":
    unittest.main()
