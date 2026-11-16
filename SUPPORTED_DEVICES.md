# Supported model profiles (experimental)

These are **documented command mappings**, not confirmed physical hardware compatibility. All devices must respond to `MODEL?` and their profile's `ROUTE?` query. The integration does not claim support for every device in a named series.

| Model | Protocol 3000 route layer | Physical input IDs | Physical destination IDs | Logical outputs | Manual |
| --- | ---: | --- | --- | ---: | --- |
| VP-440 | 12 (video + audio) | 0–5 | 1 | 1 | [Kramer VP-440 manual](https://cdn.kramerav.com/web/downloads/manuals/kramer-vp-440-um-11.pdf) |
| VP-444 | 12 (video + audio) | 0–11 | 1 (shared scaler) | 1 | [Official Kramer VP-444 manual](https://k.kramerav.com/downloads/manuals/vp-444.pdf) |
| VP-440X | 1 (video + audio) | 1–5 | 1 | 1 | [VP-440X Protocol 3000 command guide](https://cdn.kramerav.com/web/downloads/manuals/kramer-vp-440x-um-rev_5.pdf) |
| VP-558 | 1 (video) | 1–11 | 1–4 | 4 | [VP-558 ROUTE command options](https://www.manualslib.com/manual/1107652/Kramer-Vp-558.html?page=70) |
| VP-778 | 1 (video) | 0–7 | 0–1 | 2 scaler channels | [Kramer VP-778 manual](https://k.kramerav.com/downloads/manuals/kramer_vp-778.pdf) |

## Physical port mappings

### VP-440

`0=HDMI 1; 1=HDMI 2; 2=HDMI 3; 3=HDMI 4; 4=PC 1; 5=PC 2`. One scaler is destination `1`. The device's documented `ROUTE` command affects video and audio together.

### VP-444

`0–9=HDMI 1–10; 10=PC 1; 11=PC 2`. Both HDMI output connectors show the same scaler source; expose **one** Home Assistant source select, not two independently controllable outputs. Set/select the shared scaler using `ROUTE` layer **12**, destination **1**. Layer 12 routes video and audio together. VP-444 uses **UDP port 50000** for Protocol 3000 IP control (TCP is not supported); RS-232 at 9600 baud is documented but not yet implemented in KramerAV.

Example: `#ROUTE? 12,1` to read the source; `#ROUTE 12,1,2` to select HDMI 3; `#ROUTE 12,1,11` to select PC 2. Source IDs are **zero-based**.

### VP-440X

`1=HDMI 1; 2=HDMI 2; 3=HDMI 3; 4=HDMI 4; 5=PC`. One scaler is destination `1`. Layer `1` is documented as video+audio on this model.

### VP-558

`1–6=HDMI 1–6; 7–10=HDBaseT 1–4; 11=PC`. Four independently selected destinations `1–4`. HDMI/HDBaseT port details follow the device's command options table. Additional routing features for SID-X2N/SID-X3N mode are not implemented.

### VP-778

`0–3=HDMI 1–4; 4–5=DVI-U 1–2; 6–7=HDBaseT 1–2`. Scaler channel destinations `0` and `1`. Each channel's output includes an HDMI and HDBaseT connector. Transition, overlay, program/preview and TAKE operations are not fully modeled; the integration only selects each channel's video source.

## Discovery / safety

- Model IDs are matched exactly (case and whitespace ignored); an unknown suffix or variant is not assumed compatible.
- A recognized model's routing layer and first destination are confirmed by a read-only query before routes can be changed.
- Incorrect manual matrix dimensions cause a setup error rather than being silently accepted for a recognized model.
- All switching operations require feedback matching the requested logical source/destination.
- Device profile Auto may be bypassed with Generic mode for expert manual configuration, but doing so bypasses these routing safeguards.

## Test status

- Simulated network protocol and mapping tests: **yes**.
- Actual Home Assistant instance: **not tested**.
- Physical Kramer switchers/scalers: **not tested**.
- Hardware compatibility certification: **none**.

Additional models (for example VP-772, VP-732, VP-428H2 and other revisions) require a verified per-model command table before being added. Generic `ROUTE`/`VID` and extended `X-ROUTE` support may already work for some, but there are no specific verified profiles for them.

## v0.4.0 additional controls

Optional controls are enabled only after successful, parameter-matching read-only queries:

- **VP-444:** common audio mute, video enabled, freeze, front-panel lock, standby; output volume 0–100 Kramer units; resolution, auto sync off and audio delay. The latter four are described in the VP-444 manual: https://k.kramerav.com/downloads/manuals/vp-444.pdf. No live advanced-control verification yet.
- **VP-440, VP-440X, VP-558, VP-778, VS-family and other Protocol 3000 matrices:** best-effort probes for `LOCK-FP?`, `STANDBY?`, and `MUTE?`/`VMUTE?`/`VFRZ?` on 1-based output IDs. Actual functionality is **unknown until hardware-tested**. The absence of a control is not a device fault.
- Numeric volume/ranges and codec-/scaler-specific settings are intentionally **not guessed** for other models.

All model compatibility remains experimental. Please report actual model, firmware revision, transport, and which controls were observed to work; never post network credentials or private IP addresses in public reports.
