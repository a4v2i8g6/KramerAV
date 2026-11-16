"""Conservative, read-only discovery of optional Protocol 3000 controls.

Commands are supported only when a read query returns the exact expected
parameters and a valid value. No command is sent to modify hardware at setup.
Every control has its own physical address, range, and semantic meaning.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

from .protocol import KramerMessage


ControlKind = Literal["switch", "number", "select"]


@dataclass(frozen=True)
class ControlSpec:
    key: str
    name: str
    kind: ControlKind
    command: str
    address: tuple[int, ...] = ()
    minimum: int | None = None
    maximum: int | None = None
    choices: tuple[tuple[int, str], ...] = ()
    # When true a binary 1 means enabled; for video enabled this avoids an
    # ambiguous 'video mute' label where firmware uses 1=video ON.
    true_value: int = 1
    false_value: int = 0
    config: bool = False

    def get_command(self) -> str:
        args = ",".join(map(str, self.address))
        return f"{self.command}?" + (f" {args}" if args else "")

    def set_command(self, value: int) -> str:
        if not self.accepts(value):
            raise ValueError(f"{value} is outside the supported values for {self.key}")
        args = ",".join(map(str, (*self.address, value)))
        return f"{self.command} {args}"

    def accepts(self, value: object) -> bool:
        if type(value) is not int:  # bool must be converted explicitly by HA entities
            return False
        if self.kind == "switch":
            return value in (self.false_value, self.true_value)
        if self.kind == "select":
            return value in (code for code, _ in self.choices)
        return (self.minimum is not None and self.maximum is not None
                and self.minimum <= value <= self.maximum)

    def decode(self, message: KramerMessage) -> int | None:
        """Parse a full response (not merely a matching command name).

        Require the configured physical addressing so that unsolicited feedback
        from another output never completes a write to this one.
        """
        if message.command != self.command:
            return None
        fields = [part.strip() for part in message.payload.split(",")]
        if len(fields) != len(self.address) + 1:
            return None
        for expected, actual in zip(self.address, fields):
            if actual != str(expected):
                return None
        last = re.fullmatch(r"(-?\d+)(?:\s+OK)?\.?", fields[-1], re.IGNORECASE)
        if not last:
            return None
        value = int(last.group(1))
        return value if self.accepts(value) else None

    def option_label(self, code: int) -> str | None:
        return next((label for key, label in self.choices if key == code), None)

    def option_code(self, label: str) -> int | None:
        return next((key for key, option in self.choices if option == label), None)


# The VP-444's output audio volume is 0..100 Kramer units, NOT dB. Other
# models may instead use negative dB values or different channel indexes.
_VP444_RESOLUTIONS = (
    (200, "640x480 60Hz"), (201, "800x600 60Hz"),
    (202, "1024x768 60Hz"), (203, "1280x768 60Hz"),
    (204, "1360x768 60Hz"), (205, "1280x720 60Hz"),
    (206, "1280x800 60Hz"), (207, "1280x1024 60Hz"),
    (208, "1440x900 60Hz"), (209, "1400x1050 60Hz"),
    (210, "1680x1050 60Hz"), (211, "1600x1200 60Hz"),
    (212, "1920x1080 60Hz"), (213, "1920x1200 60Hz"),
    (214, "480p 60Hz"), (215, "720p 60Hz"),
    (216, "1080i 60Hz"), (217, "1080p 60Hz"),
    (218, "576p 50Hz"), (219, "720p 50Hz"),
    (220, "1080i 50Hz"), (221, "1080p 50Hz"),
    (222, "Native output 1"), (223, "Native output 2"),
)


def candidate_controls(model: str, output_count: int) -> list[ControlSpec]:
    """Return read-only query candidates, with explicit VP-444 overrides.

    Other Protocol 3000 units are probed for shared commands using standard
    1-based output numbers. The parser must confirm the exact output number.
    These common controls are best-effort, not a universal compatibility claim.
    """
    controls = [
        ControlSpec("front_panel_lock", "Front panel locked", "switch", "LOCK-FP", config=True),
        ControlSpec("standby", "Standby", "switch", "STANDBY", config=True),
    ]
    # Cap discovery to 16 outputs for large chassis. Additional per-output
    # controls should be described through explicit model profiles later.
    for output in range(1, min(output_count, 16) + 1):
        suffix = "" if output_count == 1 else f" (output {output})"
        controls.extend((
            ControlSpec(f"audio_mute_{output}", f"Audio mute{suffix}", "switch", "MUTE", (output,)),
            ControlSpec(f"video_enabled_{output}", f"Video enabled{suffix}", "switch", "VMUTE", (output,)),
            ControlSpec(f"video_freeze_{output}", f"Video freeze{suffix}", "switch", "VFRZ", (output,)),
        ))

    if model.strip().upper() == "VP-444":
        controls.extend((
            ControlSpec("output_volume", "Output volume", "number", "AUD-LVL", (1, 0), 0, 100),
            ControlSpec("auto_sync_off", "Auto sync off", "select", "SCLR-AS", (1,),
                        choices=((0, "Disabled"), (1, "Fast"), (2, "Slow")), config=True),
            ControlSpec("audio_delay", "Audio delay", "select", "SCLR-AUDIO-DELAY", (1,),
                        choices=((0, "Off"), (1, "40 ms"), (2, "110 ms"), (3, "150 ms")), config=True),
            ControlSpec("output_resolution", "Output resolution", "select", "VID-RES", (1, 1, 0),
                        choices=_VP444_RESOLUTIONS, config=True),
        ))
    return controls
