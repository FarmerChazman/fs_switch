import sys
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "apps" / "fs_switch"
sys.path.insert(0, str(APP))

from fs_switch.simulator import simulate_flow  # noqa: E402


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
        entry="answer",
    )


def menu_graph(tries=1):
    return graph(
        [
            node("menu", "menu", {
                "prompt": "ivr/main_menu.wav",
                "variable": "menu_digit",
                "tries": tries,
                "options": [
                    {"digit": "1", "label": "Sales"},
                    {"digit": "2", "label": "Support"},
                ],
            }),
            node("sales", "ring_group", {"endpoints": ["1001"]}),
            node("support", "voicemail", {"mailbox": "support"}),
            node("bye", "hangup"),
        ],
        [
            edge("e1", "menu", "sales", "digit:1"),
            edge("e2", "menu", "support", "digit:2"),
            edge("e3", "menu", "bye", "timeout"),
            edge("e4", "sales", "bye"),
        ],
        entry="menu",
    )


def time_graph(field="${strftime(%H)}", expression="^(09|10|11|12|13|14|15|16|17)$"):
    return graph(
        [
            node("time", "time", {"field": field, "expression": expression}),
            node("open", "ring_group", {"endpoints": ["1001"]}),
            node("closed", "ring_group", {"endpoints": ["1002"]}),
            node("bye", "hangup"),
        ],
        [
            edge("e1", "time", "open", "match"),
            edge("e2", "time", "closed", "no_match"),
            edge("e3", "open", "bye"),
            edge("e4", "closed", "bye"),
        ],
        entry="time",
    )


class RouteSimulatorTest(unittest.TestCase):
    def test_linear_flow_returns_every_step_and_terminal(self):
        result = simulate_flow(linear_graph())
        self.assertTrue(result["valid"])
        self.assertTrue(result["matched"])
        self.assertEqual([step["node"] for step in result["path"]], ["answer", "play", "bye"])
        self.assertEqual(result["path"][0]["port"], "next")
        self.assertIsNone(result["path"][-1]["port"])
        self.assertEqual(result["terminal"], "bye")
        self.assertEqual(result["outcome"], "Hang up")

    def test_menu_follows_the_selected_digit(self):
        result = simulate_flow(menu_graph(), digits="1")
        self.assertEqual(
            [step["node"] for step in result["path"]],
            ["menu", "sales", "bye"],
        )
        self.assertEqual(result["path"][0]["port"], "digit:1")
        self.assertIn("Sales", result["path"][0]["note"])
        self.assertEqual(result["variables"]["menu_digit"], "1")

    def test_menu_without_input_takes_timeout(self):
        result = simulate_flow(menu_graph(), digits="")
        self.assertEqual([step["node"] for step in result["path"]], ["menu", "bye"])
        self.assertEqual(result["path"][0]["port"], "timeout")
        self.assertEqual(result["variables"]["menu_digit"], "")

    def test_menu_invalid_digit_takes_timeout_after_tries(self):
        result = simulate_flow(menu_graph(tries=1), digits="9")
        self.assertEqual(result["path"][0]["port"], "timeout")
        self.assertIn("9", result["path"][0]["note"])

    def test_menu_retries_an_invalid_digit_when_tries_allows(self):
        result = simulate_flow(menu_graph(tries=2), digits="91")
        self.assertEqual(result["path"][0]["port"], "digit:1")
        self.assertEqual(result["variables"]["menu_digit"], "1")

    def test_time_condition_matches_and_does_not_match(self):
        morning = simulate_flow(time_graph(), at="2026-10-23T10:30:00")
        evening = simulate_flow(time_graph(), at="2026-10-23T20:30:00")
        self.assertEqual(morning["path"][0]["port"], "match")
        self.assertEqual([step["node"] for step in morning["path"]], ["time", "open", "bye"])
        self.assertEqual(evening["path"][0]["port"], "no_match")
        self.assertEqual([step["node"] for step in evening["path"]], ["time", "closed", "bye"])

    def test_time_field_can_read_the_destination_number(self):
        result = simulate_flow(
            time_graph(field="destination_number", expression="^1000$"),
            destination="1000",
        )
        self.assertEqual(result["path"][0]["port"], "match")

    def test_set_variable_feeds_a_later_time_condition(self):
        flow = graph(
            [
                node("set", "set", {"variable": "open", "value": "1"}),
                node("time", "time", {"field": "${open}", "expression": "^1$"}),
                node("open", "ring_group", {"endpoints": ["1001"]}),
                node("closed", "ring_group", {"endpoints": ["1002"]}),
                node("bye", "hangup"),
            ],
            [
                edge("e1", "set", "time"),
                edge("e2", "time", "open", "match"),
                edge("e3", "time", "closed", "no_match"),
                edge("e4", "open", "bye"),
                edge("e5", "closed", "bye"),
            ],
            entry="set",
        )
        result = simulate_flow(flow)
        self.assertEqual([step["node"] for step in result["path"]], ["set", "time", "open", "bye"])
        self.assertEqual(result["variables"]["open"], "1")

    def test_set_variable_expands_strftime_at_the_simulated_time(self):
        flow = graph(
            [
                node("set", "set", {"variable": "open_hour", "value": "${strftime(%H)}"}),
                node("time", "time", {"field": "${open_hour}", "expression": "^10$"}),
                node("open", "ring_group", {"endpoints": ["1001"]}),
                node("closed", "ring_group", {"endpoints": ["1002"]}),
                node("bye", "hangup"),
            ],
            [
                edge("e1", "set", "time"),
                edge("e2", "time", "open", "match"),
                edge("e3", "time", "closed", "no_match"),
                edge("e4", "open", "bye"),
                edge("e5", "closed", "bye"),
            ],
            entry="set",
        )
        result = simulate_flow(flow, at="2026-10-23T10:30:00")
        self.assertEqual(result["variables"]["open_hour"], "10")
        self.assertEqual(result["path"][1]["port"], "match")

    def test_destination_pattern_mismatch_returns_no_path(self):
        result = simulate_flow(
            linear_graph(),
            destination="9999",
            destination_number="^1000$",
        )
        self.assertTrue(result["valid"])
        self.assertFalse(result["matched"])
        self.assertEqual(result["path"], [])
        self.assertTrue(result["warnings"])

    def test_destination_pattern_match_keeps_the_path(self):
        result = simulate_flow(
            linear_graph(),
            destination="1000",
            destination_number="^1000$",
        )
        self.assertTrue(result["matched"])
        self.assertEqual([step["node"] for step in result["path"]], ["answer", "play", "bye"])

    def test_time_accepts_hhmm_and_hh_colon_mm(self):
        compact = simulate_flow(time_graph(), at="1030")
        separated = simulate_flow(time_graph(), at="10:30")
        self.assertEqual(compact["path"][0]["port"], "match")
        self.assertEqual(separated["path"][0]["port"], "match")

    def test_loops_stop_at_the_step_limit(self):
        flow = graph(
            [
                node("menu", "menu", {
                    "prompt": "ivr/main_menu.wav",
                    "options": [{"digit": "1", "label": "Sales"}],
                }),
                node("bye", "hangup"),
            ],
            [
                edge("e1", "menu", "bye", "digit:1"),
                edge("e2", "menu", "menu", "timeout"),
            ],
            entry="menu",
        )
        result = simulate_flow(flow, digits="", max_steps=3)
        self.assertEqual(len(result["path"]), 3)
        self.assertTrue(result["truncated"])
        self.assertTrue(result["warnings"])

    def test_invalid_flow_returns_validation_errors(self):
        result = simulate_flow({"schema": 1, "entry": "", "nodes": [], "edges": []})
        self.assertFalse(result["valid"])
        self.assertEqual(result["path"], [])
        self.assertTrue(result["errors"])

    def test_unknown_time_field_returns_an_error(self):
        result = simulate_flow(time_graph(field="${unknown}"))
        self.assertFalse(result["valid"])
        self.assertIn("unknown", " ".join(result["errors"]).lower())

    def test_variables_can_be_passed_as_a_json_string(self):
        result = simulate_flow(
            time_graph(field="${open}", expression="^1$"),
            variables='{"open": "1"}',
        )
        self.assertEqual(result["path"][0]["port"], "match")

    def test_invalid_time_input_raises(self):
        with self.assertRaises(ValueError):
            simulate_flow(linear_graph(), at="not-a-time")


if __name__ == "__main__":
    unittest.main()
