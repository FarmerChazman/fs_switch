import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "fs_switch"))

from fs_switch.esl import (  # noqa: E402
    _callcenter_rows,
    _channel_row,
    _enrich_queue_channel,
)


AGENT_LIST = """name|instance_id|uuid|type|contact|status|state|max_no_answer|wrap_up_time
7101@accept_a|single_box||callback|[leg_timeout=30]user/7101@accept-a.localhost|Available|Waiting|0|30
"""

QUEUE_LIST = """name|strategy|moh_sound|time_base_score|tier_rules_apply|calls_answered
accept_support@accept_a|longest-idle-agent|local_stream://moh|queue|false|3
"""


class ESLParserTest(unittest.TestCase):
    def test_agent_header_is_not_a_row_and_status_is_named(self):
        rows = _callcenter_rows(AGENT_LIST)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "7101@accept_a")
        self.assertEqual(rows[0]["status"], "Available")
        self.assertEqual(rows[0]["state"], "Waiting")
        self.assertEqual(rows[0]["type"], "callback")

    def test_queue_header_is_not_a_row(self):
        rows = _callcenter_rows(QUEUE_LIST)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "accept_support@accept_a")
        self.assertEqual(rows[0]["strategy"], "longest-idle-agent")
        self.assertEqual(rows[0]["calls_answered"], "3")

    def test_legacy_output_without_header_still_works(self):
        rows = _callcenter_rows("1001@default|Available|Waiting\n")
        self.assertEqual(rows[0]["name"], "1001@default")
        self.assertEqual(rows[0]["status"], "Available")
        self.assertEqual(rows[0]["state"], "Waiting")

    def test_status_markers_are_ignored(self):
        self.assertEqual(_callcenter_rows("+OK\n-ERR no\n"), [])

    def test_callcenter_channel_gets_queue_wait_and_agent(self):
        class FakeESL:
            def api(self, command):
                if command.endswith("cc_queue"):
                    return "support@acme\n"
                if command.endswith("cc_queue_joined_epoch"):
                    return f"{int(time.time()) - 12}\n"
                if command.endswith("cc_agent"):
                    return "7101@acme\n"
                return ""

        channel = _channel_row(
            {
                "uuid": "abc",
                "cid_num": "+14155550100",
                "application": "callcenter",
            }
        )
        _enrich_queue_channel(FakeESL(), channel)
        self.assertEqual(channel["queue"], "support@acme")
        self.assertEqual(channel["agent"], "7101@acme")
        self.assertGreaterEqual(channel["wait_seconds"], 11)


if __name__ == "__main__":
    unittest.main()
