import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1] / "apps" / "fs_switch"
sys.path.insert(0, str(APP))

from fs_switch.dialplan import compile_dialplan, compile_extension  # noqa: E402
from fs_switch.flow import (  # noqa: E402
    FlowError,
    compile_flow,
    node_catalog,
    validate_flow,
)


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


def graph(nodes, edges, entry="answer"):
    return {"schema": 1, "entry": entry, "nodes": nodes, "edges": edges}


def linear_graph():
    return graph(
        [
            node("answer", "answer"),
            node("play", "play", {"prompt": "ivr/welcome.wav"}),
            node("bye", "hangup"),
        ],
        [
            edge("e1", "answer", "play"),
            edge("e2", "play", "bye"),
        ],
    )


class SemanticFlowTest(unittest.TestCase):
    def test_linear_flow_compiles_as_state_machine(self):
        xml = compile_flow(
            linear_graph(),
            context="default",
            name="office",
            destination_number="^1000$",
        )
        self.assertIn('extension name="fs_flow_office_entry"', xml)
        self.assertIn('expression="^1000$"', xml)
        self.assertIn('data="fs_flow_office_answer XML default"', xml)
        self.assertIn('application="playback"', xml)
        self.assertIn('application="hangup"', xml)
        self.assertIn('expression="^fs_flow_office_play$"', xml)

    def test_menu_compiles_digit_and_timeout_branches(self):
        flow = graph(
            [
                node("answer", "answer"),
                node(
                    "menu",
                    "menu",
                    {
                        "prompt": "ivr/main_menu.wav",
                        "variable": "menu_digit",
                        "options": [
                            {"digit": "1", "label": "Sales"},
                            {"digit": "2", "label": "Support"},
                        ],
                    },
                ),
                node("sales", "queue", {"queue": "sales"}),
                node("support", "voicemail", {"mailbox": "support"}),
                node("bye", "hangup"),
            ],
            [
                edge("e1", "answer", "menu"),
                edge("e2", "menu", "sales", "digit:1"),
                edge("e3", "menu", "support", "digit:2"),
                edge("e4", "menu", "bye", "timeout"),
                edge("e5", "sales", "bye"),
            ],
        )
        xml = compile_flow(flow, context="default", name="main", destination_number="^2000$")
        self.assertIn('application="play_and_get_digits"', xml)
        self.assertIn('data="1 1 1 5000 # ivr/main_menu.wav', xml)
        self.assertIn("menu_digit [12]", xml)
        self.assertIn('field="${menu_digit}" expression="^1$"', xml)
        self.assertIn('field="${menu_digit}" expression="^2$"', xml)
        self.assertIn('field="${menu_digit}" expression="^$"', xml)
        self.assertIn('extension name="fs_flow_main_menu__select"', xml)
        self.assertIn('extension name="fs_flow_main_menu__select_digit_2"', xml)
        self.assertIn('extension name="fs_flow_main_menu__select_timeout"', xml)
        self.assertIn('expression="^fs_flow_main_menu__select$"', xml)
        self.assertIn('application="callcenter"', xml)
        self.assertIn('application="voicemail"', xml)

    def test_menu_rejects_multi_digit_collection(self):
        flow = graph(
            [
                node("answer", "answer"),
                node(
                    "menu",
                    "menu",
                    {
                        "prompt": "ivr/main_menu.wav",
                        "min_digits": 2,
                        "max_digits": 2,
                        "options": [{"digit": "1", "label": "Sales"}],
                    },
                ),
                node("bye", "hangup"),
            ],
            [
                edge("e1", "answer", "menu"),
                edge("e2", "menu", "bye", "digit:1"),
                edge("e3", "menu", "bye", "timeout"),
            ],
        )
        errors = validate_flow(flow)
        self.assertTrue(any("min_digits" in error for error in errors), errors)
        with self.assertRaises(FlowError):
            compile_flow(flow, context="default", name="main", destination_number="^2000$")

    def test_time_condition_emits_match_and_no_match(self):
        flow = graph(
            [
                node("answer", "answer"),
                node(
                    "hours",
                    "time",
                    {"field": "${strftime(%H%M)}", "expression": "^(09|10|11|12|13|14|15|16|17)"},
                ),
                node("open", "hangup"),
                node("closed", "hangup"),
            ],
            [
                edge("e1", "answer", "hours"),
                edge("e2", "hours", "open", "match"),
                edge("e3", "hours", "closed", "no_match"),
            ],
        )
        xml = compile_flow(flow, context="default", name="hours", destination_number="^3000$")
        self.assertIn('expression="^(09|10|11|12|13|14|15|16|17)"', xml)
        self.assertIn('expression="^.*$"', xml)

    def test_cycle_is_allowed_because_it_is_a_call_loop(self):
        flow = graph(
            [
                node("answer", "answer"),
                node("menu", "menu", {"prompt": "ivr/menu.wav", "options": ["1"]}),
                node("bye", "hangup"),
            ],
            [
                edge("e1", "answer", "menu"),
                edge("e2", "menu", "menu", "digit:1"),
                edge("e3", "menu", "bye", "timeout"),
            ],
        )
        self.assertEqual(validate_flow(flow), [])
        self.assertIn('application="play_and_get_digits"', compile_flow(flow, name="loop", destination_number="^4000$"))

    def test_missing_branch_is_rejected(self):
        flow = graph(
            [
                node("answer", "answer"),
                node("menu", "menu", {"prompt": "ivr/menu.wav", "options": ["1"]}),
                node("bye", "hangup"),
            ],
            [edge("e1", "answer", "menu")],
        )
        errors = validate_flow(flow)
        self.assertTrue(any("timeout" in error for error in errors))
        with self.assertRaises(FlowError):
            compile_flow(flow, name="bad", destination_number="^5000$")

    def test_unknown_handle_is_rejected(self):
        flow = graph(
            [
                node("answer", "answer"),
                node("menu", "menu", {"prompt": "ivr/menu.wav", "options": ["1"]}),
                node("bye", "hangup"),
            ],
            [
                edge("e1", "answer", "menu"),
                edge("e2", "menu", "bye", "digit:9"),
            ],
        )
        errors = validate_flow(flow)
        self.assertTrue(any("digit:9" in error for error in errors))

    def test_duplicate_handle_is_rejected(self):
        flow = graph(
            [
                node("answer", "answer"),
                node("menu", "menu", {"prompt": "ivr/menu.wav", "options": ["1"]}),
                node("one", "hangup"),
                node("two", "hangup"),
            ],
            [
                edge("e1", "answer", "menu"),
                edge("e2", "menu", "one", "digit:1"),
                edge("e3", "menu", "two", "digit:1"),
                edge("e4", "menu", "one", "timeout"),
            ],
        )
        errors = validate_flow(flow)
        self.assertTrue(any("more than one edge" in error for error in errors))

    def test_unknown_type_and_missing_required_data_are_reported(self):
        flow = graph([node("answer", "not-a-node")], [])
        self.assertTrue(any("unknown type" in error for error in validate_flow(flow)))

        flow = graph(
            [
                node("answer", "answer"),
                node("play", "play", {}),
                node("bye", "hangup"),
            ],
            [edge("e1", "answer", "play"), edge("e2", "play", "bye")],
        )
        self.assertTrue(any("requires 'prompt'" in error for error in validate_flow(flow)))

    def test_unreachable_node_is_rejected(self):
        flow = linear_graph()
        flow["nodes"].append(node("orphan", "hangup"))
        errors = validate_flow(flow)
        self.assertTrue(any("orphan" in error for error in errors))

    def test_terminal_node_cannot_have_outgoing_edge(self):
        flow = graph(
            [node("answer", "answer"), node("bye", "hangup")],
            [edge("e1", "answer", "bye"), edge("e2", "bye", "answer")],
        )
        errors = validate_flow(flow)
        self.assertTrue(any("terminal" in error for error in errors))

    def test_xml_escaping(self):
        flow = graph(
            [
                node("answer", "answer"),
                node("play", "play", {"prompt": "ivr/a&b.wav"}),
                node("bye", "hangup"),
            ],
            [edge("e1", "answer", "play"), edge("e2", "play", "bye")],
        )
        xml = compile_flow(flow, name="escape", destination_number="^6000$")
        self.assertIn("ivr/a&amp;b.wav", xml)
        self.assertNotIn("ivr/a&b.wav", xml)

    def test_linear_semantic_actions_compile(self):
        flow = graph(
            [
                node("answer", "answer"),
                node("set", "set", {"variable": "route", "value": "sales"}),
                node("sleep", "sleep", {"milliseconds": 250}),
                node("record", "record", {"path": "$${recordings_dir}/call.wav"}),
                node("ring", "ring_group", {"endpoints": ["1001", "1002"], "timeout_seconds": 20}),
                node("queue", "queue", {"queue": "support"}),
                node("bye", "hangup"),
            ],
            [
                edge("e1", "answer", "set"),
                edge("e2", "set", "sleep"),
                edge("e3", "sleep", "record"),
                edge("e4", "record", "ring"),
                edge("e5", "ring", "queue"),
                edge("e6", "queue", "bye"),
            ],
        )
        xml = compile_flow(flow, context="default", name="linear", destination_number="^7000$")
        self.assertIn('data="route=sales"', xml)
        self.assertIn('application="sleep" data="250"', xml)
        self.assertIn('application="record_session"', xml)
        self.assertIn(
            'data="{leg_timeout=20}user/1001@${domain_name},user/1002@${domain_name}"',
            xml,
        )
        self.assertIn('application="callcenter" data="support@default"', xml)

    def test_terminal_transfer_compiles(self):
        flow = graph(
            [node("answer", "answer"), node("out", "transfer", {"destination": "1001"})],
            [edge("e1", "answer", "out")],
        )
        xml = compile_flow(flow, name="transfer", destination_number="^7100$")
        self.assertIn('application="transfer" data="1001 XML default"', xml)

    def test_node_catalog_contains_semantic_nodes(self):
        types = {item["type"] for item in node_catalog()}
        self.assertIn("menu", types)
        self.assertIn("time", types)
        self.assertIn("queue", types)
        self.assertIn("ring_group", types)

    def test_semantic_graph_compiles_through_dialplan_adapter(self):
        plan = SimpleNamespace(
            graph=json.dumps(linear_graph()),
            graph_format="semantic",
            context="default",
            extension_name="office",
            destination_number="^1000$",
            title="Office",
        )
        xml = compile_extension(plan)
        self.assertIn('extension name="fs_flow_office_entry"', xml)
        self.assertIn('application="playback"', xml)

    def test_semantic_plan_is_wrapped_in_dialplan_document(self):
        plan = SimpleNamespace(
            graph=json.dumps(linear_graph()),
            graph_format="semantic",
            context="default",
            extension_name="office",
            destination_number="^1000$",
            title="Office",
            priority=10,
            enabled=1,
        )
        settings = SimpleNamespace(
            default_context="default",
            allow_internal_calls=0,
            main_did="",
        )
        xml = compile_dialplan([plan], settings)
        self.assertIn('<context name="default">', xml)
        self.assertIn('extension name="fs_flow_office_entry"', xml)
        self.assertIn("</document>", xml)


if __name__ == "__main__":
    unittest.main()
