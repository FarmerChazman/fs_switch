import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "fs_switch"))

from fs_switch import esl_listener  # noqa: E402


class ESLListenerTest(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.original_publish = esl_listener._publish
        self.original_tenant = esl_listener._tenant
        self.original_user = esl_listener._user_for_agent
        esl_listener._publish = lambda event, payload, user=None: self.events.append(
            (event, payload, user)
        )
        esl_listener._tenant = lambda context=None, domain=None: "acme"
        esl_listener._user_for_agent = lambda agent, tenant=None: "agent@example.com"

    def tearDown(self):
        esl_listener._publish = self.original_publish
        esl_listener._tenant = self.original_tenant
        esl_listener._user_for_agent = self.original_user

    def test_channel_event_carries_tenant_and_console_fields(self):
        esl_listener._handle(
            {
                "Event-Name": "CHANNEL_CREATE",
                "Unique-ID": "uuid-1",
                "Channel-Name": "sofia/internal/1001",
                "Caller-Caller-ID-Number": "1001",
                "Caller-Caller-ID-Name": "Front desk",
                "Caller-Destination-Number": "2000",
                "Caller-Context": "acme",
                "Channel-Call-State": "RINGING",
            }
        )
        self.assertEqual(len(self.events), 1)
        event, payload, user = self.events[0]
        self.assertEqual(event, "fs_switch_call")
        self.assertIsNone(user)
        self.assertEqual(payload["uuid"], "uuid-1")
        self.assertEqual(payload["from"], "1001")
        self.assertEqual(payload["to"], "2000")
        self.assertEqual(payload["context"], "acme")
        self.assertEqual(payload["callstate"], "RINGING")
        self.assertEqual(payload["tenant"], "acme")

    def test_agent_event_is_published_globally_with_owning_user(self):
        esl_listener._handle(
            {
                "Event-Name": "CUSTOM",
                "Event-Subclass": "callcenter::info",
                "CC-Action": "agent-status-change",
                "CC-Agent": "1001@acme",
                "CC-Agent-Status": "Available",
                "CC-Agent-State": "Waiting",
                "CC-Queue": "support@acme",
            }
        )
        self.assertEqual(len(self.events), 1)
        event, payload, user = self.events[0]
        self.assertEqual(event, "fs_switch_agent")
        self.assertIsNone(user)
        self.assertEqual(payload["agent"], "1001@acme")
        self.assertEqual(payload["status"], "Available")
        self.assertEqual(payload["user"], "agent@example.com")
        self.assertEqual(payload["tenant"], "acme")

    def test_channel_event_falls_back_to_the_channel_domain(self):
        calls = []

        def tenant(context=None, domain=None):
            calls.append((context, domain))
            return "acme"

        esl_listener._tenant = tenant
        esl_listener._handle(
            {
                "Event-Name": "CHANNEL_STATE",
                "Unique-ID": "uuid-2",
                "Channel-Name": "sofia/internal/1001@acme.example",
                "Channel-Call-State": "ACTIVE",
            }
        )
        self.assertEqual(calls, [("", "acme.example")])
        self.assertEqual(self.events[0][1]["tenant"], "acme")

    def test_agent_event_falls_back_to_the_agent_context(self):
        calls = []

        def tenant(context=None, domain=None):
            calls.append((context, domain))
            return "acme"

        esl_listener._tenant = tenant
        esl_listener._handle(
            {
                "Event-Name": "CUSTOM",
                "Event-Subclass": "callcenter::info",
                "CC-Action": "agent-status-change",
                "CC-Agent": "1001@acme",
                "CC-Agent-Status": "On Break",
            }
        )
        self.assertEqual(calls, [("acme", None)])

    def test_event_domain_uses_explicit_fields_before_the_channel_name(self):
        self.assertEqual(
            esl_listener._event_domain({"variable_domain_name": "acme.example"}),
            "acme.example",
        )
        self.assertEqual(
            esl_listener._event_domain({"Channel-Name": "sofia/internal/1001@acme.example"}),
            "acme.example",
        )
        self.assertEqual(esl_listener._event_domain({}), "")

    def test_registration_events_upsert_and_remove(self):
        esl_listener._handle(
            {
                "Event-Name": "REGISTER",
                "username": "1001",
                "realm": "acme.example",
                "contact": "sip:1001@10.0.0.5:5060",
                "network_ip": "10.0.0.5",
                "network_port": "5060",
                "expires": "300",
            }
        )
        esl_listener._handle(
            {
                "Event-Name": "UNREGISTER",
                "username": "1001",
                "realm": "acme.example",
                "contact": "sip:1001@10.0.0.5:5060",
            }
        )
        self.assertEqual([row[0] for row in self.events], [
            "fs_switch_registration",
            "fs_switch_registration",
        ])
        self.assertEqual(self.events[0][1]["action"], "register")
        self.assertEqual(self.events[0][1]["registration"]["user"], "1001")
        self.assertEqual(self.events[1][1]["action"], "unregister")
        self.assertEqual(self.events[1][1]["tenant"], "acme")

    def test_unrelated_events_are_ignored(self):
        esl_listener._handle({"Event-Name": "HEARTBEAT"})
        self.assertEqual(self.events, [])


if __name__ == "__main__":
    unittest.main()
