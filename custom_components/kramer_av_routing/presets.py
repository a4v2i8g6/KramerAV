"""Saved-preset parsing for Protocol 3000 devices (read-only discovery)."""

from __future__ import annotations

import re
from .protocol import KramerMessage

MAX_PRESET_BUTTONS = 64


def parse_saved_presets(message: KramerMessage) -> tuple[int, ...] | None:
    """Return saved IDs; None means malformed/irrelevant device feedback.

    Never guess preset ranges or generate controls for unsaved slots.
    """
    if message.command != "PRST-LST":
        return None
    payload = message.payload.strip()
    if not payload:
        return ()
    if not re.fullmatch(r"[0-9]+(?:\s*,\s*[0-9]+)*", payload):
        return None
    numbers = tuple(dict.fromkeys(int(value.strip()) for value in payload.split(",")))
    if any(not 1 <= n <= 255 for n in numbers) or len(numbers) > MAX_PRESET_BUTTONS:
        return None
    return numbers


def parse_recalled_preset(message: KramerMessage) -> int | None:
    if message.command != "PRST-RCL":
        return None
    match = re.fullmatch(r"\s*([0-9]+)(?:\s+OK)?\s*", message.payload, re.I)
    return int(match.group(1)) if match else None
