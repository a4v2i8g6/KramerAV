## 0.6.0-alpha — Protocol 2000 compatibility foundation and diagnostics

- Added a separate binary Protocol 2000 TCP backend and conservative read-only detection.
- Shared video selectors, independent audio routing when status replies are valid, and panel lock for compatible Protocol 2000 matrices.
- Generic `ROUTE`-based Protocol 3000 layer-2 audio selection; VP and X-ROUTE device restrictions remain in place.
- Added protocol/machine selector, automatic TCP/UDP port defaults, reconfigure flow, redacted diagnostics, and connection status sensor.
- Added protocol/frame/TCP/coordinator regression tests. No protocol-mode changes during discovery.
- This is an experimental, hardware-unverified feature release. See `DUAL_PROTOCOL.md`.

## 0.5.1-alpha — Display name and branding

- Renamed the Home Assistant integration display name to **Kramer AV**.
- Added bundled brand icon and light/dark logos (Home Assistant 2026.3+).
- Kept the integration domain and config entries unchanged.
- No changes to device communication, control commands, or entities.

# Changelog

## 0.5.0 (2026-11-15) — model-specific advanced audio, HDCP, and presets

- Added read-back-verified HDCP input/output controls for VP-444, and output HDCP controls for VP-558; these are disabled by default to prevent interruptions.
- Added VP-444 mic 1/2 gain, mixer and talkover modes, detailed talkover timings, image-size selector, and read-only HDMI display-connection sensors.
- Added model-specific VP-440 microphone gain/talkover and VP-558 microphone gain plus main analog output EQ bands.
- Added optional saved-preset discovery (`PRST-LST?`) and recall buttons (`PRST-RCL`), without any preset storage/deletion commands.
- Added `button` and `binary_sensor` platforms, and restricted all optional advanced controls to read-only verified queries.
- Added support for immediate rejection of generic `ERR 002` responses instead of timing out.
- Added simulated UDP and TCP device tests for HDCP/mic status, address-specific feedback, read-only discovery, and safe preset recall (42 local tests passed).
- EDID writing and real-device validation remain out of scope for this alpha release.

## 0.4.0 (2026-11-15) — optional capability-aware controls

- Added read-only capability detection for front-panel lock, standby, audio mute, video output enabled, and freeze; common controls use strictly matched output addresses and are omitted if unsupported.
- Added VP-444-specific output volume (0–100 Kramer units), output resolution (codes 200–223), auto-sync-off, and audio delay mappings.
- Added Home Assistant `switch` and `number` platforms and optional non-routing `select` entities, all on the existing Kramer device.
- Added validation of value ranges, per-control polling, unsolicited status feedback, and control-specific unavailable state without disrupting routing.
- Added general Protocol 3000 error response handling (`ERR 002`) and bounded read-only discovery timeouts.
- Added fake TCP/UDP device tests for discovery, writes and entity behavior (37 tests passing).
- Not yet verified inside a full Home Assistant installation or against live Kramer hardware for these optional controls.


## 0.3.1 (2026-11-15) — VP-444 device profile

- Added an exact-match VP-444 profile with 10 HDMI and 2 PC video inputs (physical IDs 0–11).
- Routed both mirrored HDMI outputs through the single shared scaler (destination 1) using Protocol 3000 layer 12, which switches video and audio together.
- Confirmed from the Kramer VP-444 manual that network control uses UDP (default port 50000), not TCP.
- Added TCP simulator and UDP loopback tests for correct VP-444 probing, input numbering, feedback, no writes during setup, and refusal of a false 12×2 matrix layout.
- No physical Kramer VP-444 or full Home Assistant runtime validation yet.


## 0.3.0 (2026-11-15) — experimental VP routing profiles

- Added exact model profiles for VP-440, VP-440X, VP-558 and VP-778, grounded in each model's Protocol 3000 command reference.
- Added read-only verification of profile-specific `ROUTE?` query before enabling routing writes; rejects incompatible manually specified port counts.
- Added a profile-mode setting: Auto (verified VP routing) or Generic (manual override).
- Added support for zero-based physical source/destination IDs, VP-440's route layer 12, and `ROUTE ... OK` feedback.
- Added model-specific input names and dual-scaler output channel labels with user-defined name overrides.
- Added diagnostic attributes for selected backend, active profile, route layer and physical source/destination IDs.
- Added simulated VP devices and parser/coordinator tests; 26 tests passed locally before final test additions.
- Not yet validated against real Kramer devices or full Home Assistant environment.

## 0.2.0 (2026-11-15) — experimental Extended Protocol 3000

- Added typed signal ID parsing, including video-only `SIGNALS-LIST?` discovery and full/abbreviated signal IDs.
- Added read-only Extended `X-ROUTE?` probing and fallback to existing `ROUTE`/`VID` families.
- Added `X-ROUTE` crosspoint writes with confirmation against received routing feedback.
- Added physical connector type and port number to Home Assistant output/input labels for extended devices.
- Added stable physical output unique IDs for X-ROUTE devices.
- Added extended protocol and coordinator tests with simulated matrix devices; 15 local tests passing on Python 3.13.
- Included GitHub Actions test/validation workflow from earlier project milestone.
- Still requires real Kramer hardware testing, CI validation and device profiles.

## 0.1.0 (2026-11-15) — prototype

- Home Assistant UI configuration and selectable TCP/UDP transport.
- Protocol 3000 model probing, optional IO count discovery.
- Generic ROUTE/VID video output switching with query and confirmation.
- One Select entity per output, polling and spontaneous feedback listener.
- Input/output labels, reconnection and simulated-device protocol tests.

Not tested on physical Kramer hardware or a running Home Assistant instance.
