"""Conservative model-specific Protocol 3000 ROUTE mappings.

This module deliberately matches exact model identifiers. Kramer sometimes uses
zero-based source/scaler IDs or different ROUTE layers on VP products; do not
infer a mapping from a shared VP prefix.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VPProfile:
    model: str
    route_layer: int
    input_ids: tuple[int, ...]
    output_ids: tuple[int, ...]
    input_labels: tuple[str, ...]
    output_labels: tuple[str, ...]
    manual_url: str

    def __post_init__(self) -> None:
        if not self.input_ids or not self.output_ids:
            raise ValueError("Profile must have routable inputs and outputs")
        if len(self.input_ids) != len(self.input_labels):
            raise ValueError("Input labels do not match input IDs")
        if len(self.output_ids) != len(self.output_labels):
            raise ValueError("Output labels do not match output IDs")
        if len(set(self.input_ids)) != len(self.input_ids):
            raise ValueError("Duplicate input IDs")
        if len(set(self.output_ids)) != len(self.output_ids):
            raise ValueError("Duplicate output IDs")


# Each profile is based on a device-specific Kramer Protocol 3000 command table.
PROFILES = {
    "VP-440": VPProfile(
        "VP-440", 12, (0, 1, 2, 3, 4, 5), (1,),
        ("HDMI 1", "HDMI 2", "HDMI 3", "HDMI 4", "PC 1", "PC 2"),
        ("Scaler",),
        "https://cdn.kramerav.com/web/downloads/manuals/kramer-vp-440-um-11.pdf",
    ),
    "VP-444": VPProfile(
        "VP-444", 12, tuple(range(12)), (1,),
        tuple(f"HDMI {index}" for index in range(1, 11)) + ("PC 1", "PC 2"),
        ("Scaler (HDMI outputs 1 + 2)",),
        "https://k.kramerav.com/downloads/manuals/vp-444.pdf",
    ),
    "VP-440X": VPProfile(
        "VP-440X", 1, (1, 2, 3, 4, 5), (1,),
        ("HDMI 1", "HDMI 2", "HDMI 3", "HDMI 4", "PC"),
        ("Scaler",),
        "https://cdn.kramerav.com/web/downloads/manuals/kramer-vp-440x-um-rev_5.pdf",
    ),
    "VP-558": VPProfile(
        "VP-558", 1, tuple(range(1, 12)), tuple(range(1, 5)),
        tuple(f"HDMI {i}" for i in range(1, 7))
        + tuple(f"HDBaseT {i}" for i in range(1, 5)) + ("PC",),
        tuple(f"Output {i}" for i in range(1, 5)),
        "https://www.manualslib.com/manual/1107652/Kramer-Vp-558.html?page=70",
    ),
    "VP-778": VPProfile(
        "VP-778", 1, tuple(range(8)), (0, 1),
        ("HDMI 1", "HDMI 2", "HDMI 3", "HDMI 4", "DVI-U 1", "DVI-U 2", "HDBaseT 1", "HDBaseT 2"),
        ("Channel 1 (HDMI + HDBaseT)", "Channel 2 (HDMI + HDBaseT)"),
        "https://k.kramerav.com/downloads/manuals/kramer_vp-778.pdf",
    ),
}


def profile_for_model(model: str) -> VPProfile | None:
    """Choose a profile only for an exact model ID, ignoring case/whitespace."""
    return PROFILES.get(model.strip().upper())
