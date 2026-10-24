import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1] / "apps" / "fs_switch"
sys.path.insert(0, str(APP))

from fs_switch.dialplan import (  # noqa: E402
    NOT_FOUND_DOCUMENT,
    DialplanError,
    compile_dialplan,
    compile_extension,
    compile_published_dialplan,
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

    def test_compile_published_dialplan_uses_only_published_xml(self):
        published = SimpleNamespace(
            title="Published",
            enabled=1,
            published_context="default",
            published_priority=10,
            published_xml='    <extension name="published_only"><condition field="destination_number" expression="^1000$"/></extension>',
            graph=graph([node("draft", "answer")], []),
            graph_format="raw",
            context="default",
            priority=10,
        )
        settings = SimpleNamespace(
            default_context="default",
            main_did="",
            allow_internal_calls=0,
        )
        xml = compile_published_dialplan([published], settings)
        self.assertIn('extension name="published_only"', xml)
        self.assertNotIn('extension name="draft"', xml)
        self.assertNotIn("application=", xml)

    def test_published_dialplan_can_alias_a_generic_webrtc_context(self):
        plan = SimpleNamespace(
            title="WebRTC",
            enabled=1,
            published_context="accept_a",
            published_priority=10,
            published_xml='    <extension name="webrtc_flow"><condition field="destination_number" expression="^9300$"/></extension>',
        )
        settings = SimpleNamespace(
            default_context="default",
            main_did="",
            allow_internal_calls=1,
        )
        xml = compile_published_dialplan(
            [plan],
            settings,
            alias_context="default",
            alias_source="accept_a",
        )
        self.assertIn('<context name="accept_a">', xml)
        self.assertIn('<context name="default">', xml)
        self.assertEqual(xml.count('extension name="webrtc_flow"'), 2)

    def test_compile_published_dialplan_orders_by_published_priority(self):
        def plan(title, priority):
            return SimpleNamespace(
                title=title,
                enabled=1,
                published_context="default",
                published_priority=priority,
                published_xml=f'    <extension name="{title}"/>',
            )

        settings = SimpleNamespace(
            default_context="default",
            main_did="",
            allow_internal_calls=0,
        )
        xml = compile_published_dialplan([plan("later", 20), plan("earlier", 10)], settings)
        self.assertLess(xml.index('extension name="earlier"'), xml.index('extension name="later"'))

    def test_compile_published_dialplan_skips_enabled_without_published_xml(self):
        plan = SimpleNamespace(
            title="Draft only",
            enabled=1,
            published_context="default",
            published_priority=10,
            published_xml="",
        )
        settings = SimpleNamespace(
            default_context="default",
            main_did="",
            allow_internal_calls=0,
        )
        self.assertEqual(
            compile_published_dialplan([plan], settings),
            NOT_FOUND_DOCUMENT,
        )


if __name__ == "__main__":
    unittest.main()
