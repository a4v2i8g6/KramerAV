# KramerAV — Kramer Protocol 3000 routing for Home Assistant

**Version 0.3.1 — experimental / alpha. No real Kramer hardware has been tested.**

A Home Assistant custom integration for Kramer Protocol 3000 AV matrices and presentation switchers.

- Supports TCP (often port 5000) and UDP (often port 50000), with manually configurable ports.
- Detects device identity using `MODEL?`.
- **NEW:** Includes exact-match, read-only verified ROUTE profiles for VP-440, VP-444, VP-440X, VP-558, and VP-778.
- **NEW:** Corrects VP-specific zero/one-based input and output IDs and unusual route layers (VP-440 layer 12).
- **NEW:** Labels sources by their actual connector type (HDMI, PC, DVI-U, HDBaseT), with user override support.
- **NEW:** Treats VP-778 as a two-channel dual scaler, not four independent HDMI/HDBT destinations.
- **NEW:** Exposes active profile, route layer, and physical port IDs as output entity attributes.
- **NEW:** Automatically probes Extended Protocol 3000 using `SIGNALS-LIST?` and `X-ROUTE?`.
- **NEW:** Uses typed physical signal IDs (for example `IN.HDMI.2.VIDEO.1` and `OUT.HDBT.4.VIDEO.1`).
- **NEW:** Filters audio signals out of the video-routing selectors and distinguishes different connector types that use the same physical port number.
- Retains fallback detection of legacy `ROUTE` and `VID` command families.
- Provides one Home Assistant `select` entity for each output and live feedback for recognized video crosspoint updates.
- Supports user-defined labels and periodic routing-status refresh.
- Installs separately from the original Protocol 2000 integration; no Protocol 2000 or `kessler-av` dependency.

## Compatibility notes

This is *not* verified universal support for all VS, VP, MTX or Kramer devices. Protocol 3000 is a command protocol, not a guarantee of identical commands or capabilities. **Five specific VP models have now been mapped**, but other VP/scaler outputs, modular chassis, input groups or switchers still require documented model-specific profiles. Devices may advertise signals that are not routable with every output. Authentication and RS-232 devices are not covered yet.

**The automatic Extended Protocol 3000 detection is deliberately read-only:** it obtains `SIGNALS-LIST?`, then queries `X-ROUTE?` for the first reported video output. If this succeeds, typed ports are used for routing. Otherwise, Auto mode falls back to legacy `ROUTE?` / `VID?` discovery. An explicit `x_route` selection does not silently downgrade.

For X-ROUTE devices, logical `Input 1`, `Input 2` and `Output 1`, `Output 2` refer to the order of the VIDEO signals returned by `SIGNALS-LIST?`, **not necessarily the printed port number**. The UI appends the physical connector name (for example `Input 2 (HDMI 2)` and `Output 1 (HDBT 4)`). X-ROUTE output entity unique IDs are tied to physical signal IDs.

## VP device profiles (0.3.1)

| MODEL? response | Sources | Home Assistant outputs | Routing details |
| --- | ---: | ---: | --- |
| VP-440 | 6 | 1 | `ROUTE` layer **12**, inputs 0–5; HDMI 1–4, PC 1–2 |
| VP-444 | 12 | 1 shared scaler | `ROUTE` layer **12**, inputs 0–11; HDMI 1–10, PC 1–2; UDP only |
| VP-440X | 5 | 1 | `ROUTE` layer **1**, inputs 1–5; HDMI 1–4, PC |
| VP-558 | 11 | 4 | `ROUTE` layer **1**, inputs 1–11; HDMI 1–6, HDBaseT 1–4, PC |
| VP-778 | 8 | 2 channels | `ROUTE` layer **1**, inputs 0–7, scaler destinations **0 and 1**; HDMI 1–4, DVI-U 1–2, HDBaseT 1–2 |

**Model profiles activate only for an exact `MODEL?` identifier**, on Auto or ROUTE routing family when `profile_mode` is Auto. For those models the setup performs a read-only `ROUTE?` query to verify the expected routing layer and physical IDs. The integration refuses to activate an unconfirmed profile, rather than sending possibly incorrect switch commands. This is a *command-convention check*, not a guarantee that all sources are wired/routable or that the model's firmware matches the tested documentation.

For a known model, input/output counts can remain `0`; the profile provides the logical counts. If provided manually, they must match the profile. If a known model uses unusual firmware, select **Generic** profile mode and explicitly configure its routing family and counts **only after checking the actual device's manual**. This bypasses VP safeguards and may route incorrectly if physical numbering differs.

VP-440 and VP-444 both use layer 12, which switches **video and audio together**, not independent video-only routing. VP-778's two logical scaler channels each feed HDMI and HDBaseT connectors, and their presentation/overlay behavior depends on the device mode; changing a channel's input is not the same as executing a transition TAKE operation. Presets, TAKE, and other presentation-mode controls are not included.

See [SUPPORTED_DEVICES.md](SUPPORTED_DEVICES.md) for documentation sources and test status.

## Manual installation / upgrade

1. Download the source ZIP from the repository or the supplied alpha package.
2. Copy `custom_components/kramer_av_routing` into Home Assistant's `/config/custom_components/` folder, replacing the previous folder if upgrading.
3. Restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and select **Kramer AV Routing (Protocol 3000)**.
5. Enter the host/IP, transport, and port. **TCP often uses 5000; UDP often uses 50000**, depending on device model.
6. Leave input and output counts at `0` for auto detection, including known VP profiles. Select **Auto** routing family and **Auto** device profile mode (default). Probe order is Extended → verified VP model profile → generic ROUTE → VID. Use **Generic** profile mode only if you need to bypass known VP model routing conventions after consulting the manual.
7. In the integration's **Configure** options, supply optional comma-separated input and output names and a polling interval.

**Existing v0.1.0 entries:** Home Assistant may need a configuration entry reload/restart after upgrade. When a device changes from the legacy routing family to X-ROUTE, its output entity unique IDs change intentionally to stable physical signal IDs. Re-check automations and dashboard entity references after reconfiguration.

### VP-444 setup (UDP-only)

For a **VP-444**, select **UDP** and port **50000** when adding the integration. TCP is not available on this model. Leave **Inputs = 0** and **Outputs = 0**, select **Auto** command family and **Auto** device profile. After the read-only profile verification, the device should expose **one source selector** (12 sources), controlling the shared scaler feeding both HDMI output connectors.

Source mapping is HDMI 1–10 = physical IDs 0–9; PC 1–2 = physical IDs 10–11. A normal source choice uses `#ROUTE 12,1,<physical input>`; layer 12 changes audio and video together. This integration does not yet control VP-444 volume, microphone mixing, or independent audio processing. The exact model must report `MODEL VP-444` and respond to `ROUTE? 12,1` for automatic profile activation. See the [official VP-444 manual](https://k.kramerav.com/downloads/manuals/vp-444.pdf).

## VP-specific command examples## VP-specific command examples

The physical IDs are *not* the same as the Home Assistant 1-based selector positions:

```text
# VP-440: select HDMI 2 (physical input 1) on scaler 1, layer 12
#ROUTE 12,1,1
# VP-558: select PC (physical input 11) for output 4
#ROUTE 1,4,11
# VP-778: select HDBaseT 2 (physical input 7) on scaler channel 2 (physical dest 1)
#ROUTE 1,1,7
```

## Example commands

All examples use a carriage return (`\r`) terminator. Supported commands depend on the device.

```text
#SIGNALS-LIST?
~01@SIGNALS-LIST [IN.HDMI.1.VIDEO.1,IN.HDMI.2.VIDEO.1,OUT.HDBT.4.VIDEO.1]
#X-ROUTE? OUT.HDBT.4.VIDEO.1
~01@X-ROUTE OUT.HDBT.4.VIDEO.1,IN.HDMI.1.VIDEO.1
#X-ROUTE OUT.HDBT.4.VIDEO.1,IN.HDMI.2.VIDEO.1
~01@X-ROUTE OUT.HDBT.4.VIDEO.1,IN.HDMI.2.VIDEO.1
```

Legacy routing remains supported:

```text
#ROUTE? 1,3
#ROUTE 1,3,2
#VID? 3
#VID 2>3
```

Example Home Assistant automation (replace the entity ID and option with the actual values shown in Home Assistant):

```yaml
action: select.select_option
target:
  entity_id: select.kramer_output_1
data:
  option: "Input 2 (HDMI 2)"
```

## Testing and logging

Run the hardware-free tests from the repository root:

```bash
python -m unittest discover -s tests -v
python -m compileall -q custom_components/kramer_av_routing
```

The test suite includes TCP/UDP protocol simulation, Extended signal-ID parsing, status feedback, legacy fallback, VP profile mappings (including 0-based destinations/inputs and layer 12), and coordinator/entity route handling using lightweight Home Assistant test stubs. It does not replace full Home Assistant integration or real-device testing.

Enable optional logging in `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.kramer_av_routing: debug
```

The included `.github/workflows/validate.yml` adds automated Python tests and Home Assistant/HACS validation on GitHub Actions. These remote validators have not yet run against this version; they may identify additional fixes.

## Not implemented yet

- Independent audio routing and audio-follow-video controls.
- RS-232/serial, authenticated connections, TLS.
- Presets, signal detection, scaler controls, EDID, auto-switch controls.
- Routed subset discovery and user-selectable signal/port filtering for complex modular devices.
- Per-model routing restrictions, multiple destinations, nonstandard source/destination semantics.
- More hardware profiles and validated compatibility lists (only the five documented VP profiles above currently exist).

## Reference

- [Kramer Protocol 3000 Reference Guide (v3.0)](https://k.kramerav.com/downloads/protocols/protocol_3000_3.0_master_user.pdf)
- [Original Protocol 2000 Home Assistant integration](https://github.com/krohrbaugh/kramer-homeassistant) (inspiration only)

MIT licensed. Independent community project; not affiliated with Kramer Electronics.
