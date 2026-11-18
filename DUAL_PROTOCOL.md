# Kramer AV v0.6.0-alpha — dual-protocol development release

## Important scope

This release adds a **first Protocol 2000 TCP backend**, not blanket certification
of every Protocol 2000 model. Protocol 3000's original routing, VP profiles,
media controls, HACS branding and device IDs remain unchanged. The integration
still uses the existing `kramer_av_routing` domain to avoid breaking installations.

### Implemented in this build

- Protocol choice: Auto (read-only probe of Protocol 3000 then Protocol 2000 on TCP),
  Protocol 3000, or Protocol 2000.
- Protocol 2000 binary TCP transport with machine ID (1–31) and streaming frame
  alignment, rejection of wrong-machine frames, command serialization, and
  protocol-error handling.
- Read-only discovery of Protocol 2000 video matrix dimensions (instruction 62).
- Protocol 2000 independent video and audio output selectors, with **audio
  exposed only after a valid layer-specific status response** (instructions 5/6).
- Protocol 2000 video/audio route write with matching echo acknowledgement
  (instructions 1/2), input 0 disconnect, front-panel lock query/set (31/30).
- Generic Protocol 3000 `ROUTE`-family audio selectors based on confirmed
  `ROUTE? 2,<output>`; **not** extrapolated to VP model profiles or X-ROUTE.
- Home Assistant reconfiguration of IP/port/transport without deleting entries,
  with conservative device/protocol identity check.
- Port field accepts **0** for transport-aware defaults: TCP 5000, UDP 50000.
- Read-only downloadable diagnostics (no host/IP, credentials, or raw messages).
- Connection `binary_sensor` reflects successful polling, not just an open UDP socket.
- Existing Github Actions validation workflow included in the package.

### Setup examples

**VP-444:** Protocol 3000; UDP; port 0 (resolves to 50000); Auto routing/profile;
Input/output counts 0.

**Older IP-enabled Protocol 2000 matrix:** Protocol 2000 or Auto; TCP; device
port (default 5000 if 0); machine ID 1 unless configured differently; counts 0.

Devices that are **serial-only** cannot use this release. Protocol 2000 status
identification requires a device that accepts instruction 62 and responds.

Existing Protocol 3000 config entries have no `protocol` field; code treats
this as Protocol 3000 to preserve their behavior. No re-add is required to upgrade
those installations. For a protocol switch, remove and re-add the entry.

### Safety

No protocol-mode change, device reset, broadcast, preset-save, or EDID write is
sent during discovery. Detection can fail harmlessly on firmware that lacks
standard commands. Test routing with a physical device before using automations.

### Still pending / deliberate restrictions

- RS-232/USB serial and devices that support only serial communication.
- Universal audio breakaway and audio-follow-video state/mode control: currently
  only read-verified Protocol 2000 audio matrix and generic layer-2 Protocol 3000.
- Advanced EDID editing, safe EDID backup/restore, firmware-specific HDCP and
  scaler mappings, input signal sensors beyond existing mapped models.
- Protocol 2000 presets and AFV mode; support should be proven per model.
- Extended X-ROUTE AUDIO routing and modular-matrix port/signal constraints.
- Additional verified VP/VS model profiles, physical hardware validation.
- Real Home Assistant runtime/hassfest/HACS CI execution on this build.

**Do not publish as stable until the above boundaries are addressed and the
first physical Protocol 2000 device has been tested.**

### Source documentation

- Kramer Protocol 2000 revision 0.51:
  https://cdn.kramerav.com/web/downloads/manuals/protocol_2000_rev0_51.pdf
- Kramer Protocol 3000 reference:
  https://k.kramerav.com/downloads/protocols/protocol_3000_3.0_master_user.pdf
- Existing Protocol 2000 integration for comparison (MIT licensed; source not copied):
  https://github.com/krohrbaugh/kramer-homeassistant
