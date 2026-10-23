"""One-time setup and container configuration for a new site."""

import json
import os

import frappe

from fs_switch.publish import publish_flow
from fs_switch.tenants import DEFAULT_TENANT, ensure_default_tenant


def configure_from_env():
	"""Apply the values the container shares with FreeSWITCH.

	This is safe to run on every start. Password fields are only written when the
	environment actually contains a value, so a manual install is not wiped.
	"""
	settings = frappe.get_single("FS Switch Settings")
	settings.default_tenant = (
		os.environ.get("FS_SWITCH_DEFAULT_TENANT") or settings.default_tenant or DEFAULT_TENANT
	)
	settings.main_did = os.environ.get("FS_SWITCH_MAIN_DID") or settings.main_did or "1000"
	settings.default_context = (
		os.environ.get("FS_SWITCH_DEFAULT_CONTEXT") or settings.default_context or "default"
	)
	settings.sip_domain = os.environ.get("FS_SWITCH_SIP_DOMAIN") or settings.sip_domain or "localhost"
	settings.webrtc_url = (
		os.environ.get("FS_SWITCH_WEBRTC_URL") or settings.webrtc_url or "ws://localhost:5066"
	)
	settings.public_ip = os.environ.get("FS_SWITCH_PUBLIC_IP") or settings.public_ip or "127.0.0.1"
	settings.esl_host = os.environ.get("FS_SWITCH_ESL_HOST") or settings.esl_host or "127.0.0.1"
	settings.esl_port = int(os.environ.get("FS_SWITCH_ESL_PORT") or settings.esl_port or 8021)
	settings.xml_curl_secret = (
		os.environ.get("FS_SWITCH_XML_CURL_SECRET") or settings.get_password(
			"xml_curl_secret", raise_exception=False
		) or ""
	)
	settings.esl_password = (
		os.environ.get("FS_SWITCH_ESL_PASSWORD") or settings.get_password(
			"esl_password", raise_exception=False
		) or ""
	)
	settings.save(ignore_permissions=True)
	frappe.db.commit()
	return settings


def after_install():
	ensure_default_tenant()
	configure_from_env()
	seed_demo_dialplan()
	frappe.db.commit()


def seed_demo_dialplan():
	"""Add a disabled example so a new console is not an empty page."""
	title = "Demo inbound route"
	if frappe.db.exists("FS Dialplan", title):
		return

	graph = {
		"nodes": [
			{
				"id": "answer",
				"type": "fs-node",
				"position": {"x": 120, "y": 80},
				"data": {"label": "Answer", "application": "answer", "data": ""},
			},
			{
				"id": "greeting",
				"type": "fs-node",
				"position": {"x": 120, "y": 240},
				"data": {
					"label": "Play greeting",
					"application": "playback",
					"data": "ivr/ivr-welcome_to_freeswitch.wav",
				},
			},
			{
				"id": "hangup",
				"type": "fs-node",
				"position": {"x": 120, "y": 400},
				"data": {"label": "Hang up", "application": "hangup", "data": ""},
			},
		],
		"edges": [
			{"id": "e-answer-greeting", "source": "answer", "target": "greeting"},
			{"id": "e-greeting-hangup", "source": "greeting", "target": "hangup"},
		],
	}

	doc = frappe.get_doc(
		{
			"doctype": "FS Dialplan",
			"title": title,
			"tenant": DEFAULT_TENANT,
			"context": "default",
			"extension_name": "demo_inbound",
			"destination_number": "^1000$",
			"priority": 10,
			"enabled": 0,
			"graph_format": "raw",
			"description": "Disabled example. Enable it after setting the main DID and a greeting.",
			"graph": json.dumps(graph, indent=2),
		}
	).insert(ignore_permissions=True)
	publish_flow(doc, note="Seeded demo", published_by="Administrator")
	doc.save(ignore_permissions=True)
