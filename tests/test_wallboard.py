import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "fs_switch"))

from fs_switch.wallboard import channel_path, summarize  # noqa: E402


class WallboardTest(unittest.TestCase):
    def setUp(self):
        self.live = {
            "queues": [
                {
                    "name": "support@acme",
                    "waiting": "2",
                    "calls_answered": "8",
                    "calls_abandoned": "2",
                    "max_wait_time": "180",
                }
            ],
            "agents": [
                {"name": "7101@acme", "status": "Available", "state": "Waiting"},
                {"name": "7102@acme", "status": "On Break", "state": "Idle"},
                {"name": "7103@acme", "status": "Logged Out", "state": "Idle"},
            ],
            "channels": [
                {
                    "uuid": "abc",
                    "cid_num": "+14155550100",
                    "dest": "support@acme",
                    "queue": "support@acme",
                    "agent": "7101@acme",
                    "wait_seconds": 12,
                    "callstate": "CS_EXECUTE",
                }
            ],
        }

    def test_queue_metrics_are_tenant_summaries(self):
        result = summarize(self.live)
        self.assertEqual(result["metrics"]["waiting"], 2)
        self.assertEqual(result["metrics"]["available_agents"], 1)
        self.assertEqual(result["metrics"]["on_break"], 1)
        self.assertEqual(result["metrics"]["logged_out"], 1)
        self.assertEqual(result["metrics"]["answered"], 8)
        self.assertEqual(result["metrics"]["abandoned"], 2)
        self.assertEqual(result["metrics"]["answer_rate"], 80)
        self.assertEqual(result["metrics"]["longest_wait_seconds"], 12)
        self.assertEqual(result["metrics"]["active_calls"], 1)
        self.assertEqual(result["metrics"]["queue_calls"], 1)
        self.assertEqual(result["queues"][0]["queue"], "support")
        self.assertEqual(result["queues"][0]["context"], "acme")

    def test_call_path_prefers_queue_and_agent(self):
        self.assertEqual(
            channel_path(self.live["channels"][0]),
            "+14155550100 \u2192 support@acme \u2192 7101@acme",
        )
        self.assertEqual(
            channel_path({"cid_num": "1001", "dest": "1002"}),
            "1001 \u2192 1002",
        )

    def test_empty_snapshot_has_zeroed_metrics(self):
        result = summarize({})
        self.assertEqual(result["queues"], [])
        self.assertEqual(result["calls"], [])
        self.assertEqual(result["metrics"]["waiting"], 0)
        self.assertEqual(result["metrics"]["active_calls"], 0)
        self.assertEqual(result["metrics"]["answer_rate"], 0)


if __name__ == "__main__":
    unittest.main()
