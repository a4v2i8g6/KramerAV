# KramerAV — Kramer Protocol 3000 routing for Home Assistant

**Version 0.2.0 — experimental / alpha. No real Kramer hardware has been tested.**

A Home Assistant custom integration for Kramer Protocol 3000 AV matrices and presentation switchers.

- Supports TCP (often port 5000) and UDP (often port 50000), with manually configurable ports.
- Detects device identity using `MODEL?`.
- **NEW:** Automatically probes Extended Protocol 3000 using `SIGNALS-LIST?` and `X-ROUTE?`.
- **NEW:** Uses typed physical signal IDs (for example `IN.HDMI.2.VIDEO.1` and `OUT.HDBT.4.VIDEO.1`).
- **NEW:** Filters audio signals out of the video-routing selectors and distinguishes different connector types that use the same physical port number.
- Retains fallback detection of legacy `ROUTE` and `VID` command families.
- Provides one Home Assistant `select` entity for each output and live feedback for recognized video crosspoint updates.
- Supports user-defined labels and periodic routing-status refresh.
- Installs separately from the original Protocol 2000 integration; no Protocol 2000 or `kessler-av` dependency.

## Compatibility notes

This is *not* verified universal support for all VS, VP, MTX or Kramer devices. Protocol 3000 is a command protocol, not a guarantee of identical commands or capabilities. Some VP/scaler outputs, modular chassis, input groups or switchers require model-specific routing profiles. Devices may advertise signals that are not routable with every output. Authentication and RS-232 devices are not covered yet.

**The automatic Extended Protocol 3000 detection is deliberately read-only:** it obtains `SIGNALS-LIST?`, then queries `X-ROUTE?` for the first reported video output. If this succeeds, typed ports are used for routing. Otherwise, Auto mode falls back to legacy `ROUTE?` / `VID?` discovery. An explicit `x_route` selection does not silently downgrade.

For X-ROUTE devices, logical `Input 1`, `Input 2` and `Output 1`, `Output 2` refer to the order of the VIDEO signals returned by `SIGNALS-LIST?`, **not necessarily the printed port number**. The UI appends the physical connector name (for example `Input 2 (HDMI 2)` and `Output 1 (HDBT 4)`). X-ROUTE output entity unique IDs are tied to physical signal IDs.

## Manual installation / upgrade

1. Download the source ZIP from the repository or the supplied alpha package.
2. Copy `custom_components/kramer_av_routing` into Home Assistant's `/config/custom_components/` folder, replacing the previous folder if upgrading.
3. Restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and select **Kramer AV Routing (Protocol 3000)**.
5. Enter the host/IP, transport, and port. **TCP often uses 5000; UDP often uses 50000**, depending on device model.
6. Leave input and output counts at `0` for auto detection, or specify them if the device doesn't report its counts. Select Auto routing family for the Extended → ROUTE → VID probing sequence.
7. In the integration's **Configure** options, supply optional comma-separated input and output names and a polling interval.

**Existing v0.1.0 entries:** Home Assistant may need a configuration entry reload/restart after upgrade. When a device changes from the legacy routing family to X-ROUTE, its output entity unique IDs change intentionally to stable physical signal IDs. Re-check automations and dashboard entity references after reconfiguration.

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

The test suite includes TCP/UDP protocol simulation, Extended signal-ID parsing, status feedback, legacy fallback, and coordinator/entity route handling using lightweight Home Assistant test stubs. It does not replace full Home Assistant integration or real-device testing.

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
- Hardware profiles and validated compatibility lists.

## Reference

- [Kramer Protocol 3000 Reference Guide (v3.0)](https://k.kramerav.com/downloads/protocols/protocol_3000_3.0_master_user.pdf)
- [Original Protocol 2000 Home Assistant integration](https://github.com/krohrbaugh/kramer-homeassistant) (inspiration only)

MIT licensed. Independent community project; not affiliated with Kramer Electronics.
