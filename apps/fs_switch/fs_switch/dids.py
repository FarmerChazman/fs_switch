"""DID helpers.

DIDs are stored in the carrier's dialable form with spaces, punctuation and an
optional ``tel:`` prefix removed. The leading plus is kept so the inventory and
the dialplan pattern can agree on the same number.
"""

from __future__ import annotations

import re


def normalize_did(value) -> str:
	text = str(value or "").strip()
	if text.lower().startswith("tel:"):
		text = text[4:].strip()
	if not text:
		return ""
	return re.sub(r"[\s\-().]", "", text)


def did_key(value) -> str:
	"""Comparison key that ignores a leading plus and formatting."""
	return re.sub(r"[^0-9]", "", normalize_did(value))
