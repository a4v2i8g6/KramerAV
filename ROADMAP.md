# Kramer AV development plan (Protocol 2000 and 3000)

This is a staged implementation plan, **not** a declaration that every feature
already works across every Kramer model. Each feature is enabled only when a
safe read-only query and documented parameter mapping supports it.

## v0.6.0-alpha: Combined foundation — coded; simulated only

- Two separate TCP-based protocol engines: binary Protocol 2000 and ASCII
  Protocol 3000 (existing 3000 UDP retained).
- Video routing and source selectors shared across engines.
- Independent audio routing where read-back supports it (Protocol 2000 audio
  matrix status, generic Protocol 3000 `ROUTE` layer 2).
- Read-only discovery, basic automatic protocol choice, device reconfiguration,
  transport-aware port defaults, machine ID, diagnostics, connection sensor.
- Existing VP-440/444/440X/558/778 Protocol 3000 profiles and optional controls
  preserved. CI workflow packaged.

## Next: connection reliability and hardware matrix

- Validate latest Home Assistant runtime, HACS and hassfest action output.
- Test one or more physical Protocol 2000 TCP switchers: models, machine IDs,
  routing 0, independent audio, disconnect/reconnect, front-panel events.
- Test VP-444: query/write status for all documented controls and reboot recovery.
- Remove or fix behaviors that fail verified hardware; record model, firmware,
  transport, and confidence in `SUPPORTED_DEVICES.md`.
- Add an explicit protocol diagnostics action logging redacted last command type,
  counters, and response latency (do not export device IP or raw payloads).

## v0.7: Broader AV control

- Protocol 2000 audio-follow-video/breakaway control where documented.
- Protocol 2000 preset discovery/recall, per-model special commands.
- Protocol 3000 X-ROUTE audio with signal-ID mapping and routability constraints.
- Signal detection where read-only commands and input numbering are confirmed.
- Further VP/VS profiles and firmware-sensitive scaler, HDCP, audio controls.

## v0.8: Advanced and serial

- RS-232/USB serial transport (serial port devices cannot connect via TCP/UDP).
- Per-model EDID read/backup, explicit confirmation for writes, restore path.
- Safe preset save / delete with explicit user confirmation.
- More modular chassis profiles, port-type filtering and physical signal maps.

## v1.0: Stable release gate

- Runtime compatibility and CI validation passing.
- Hardware-backed support matrix for every advertised compatible model.
- Error recovery and capabilities verified across mixed VLAN/network conditions.
- Backward-compatible upgrade tests, HACS installation, documentation, release tagging.

Not all models offer every feature: Protocol 2000 and Protocol 3000 share an
interface, not identical capabilities. Device-specific support remains necessary.
