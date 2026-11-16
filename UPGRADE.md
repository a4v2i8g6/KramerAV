# Upgrade to KramerAV v0.5.0-alpha

## From v0.4.0-alpha or earlier

1. Back up the Home Assistant folder `/config/custom_components/kramer_av_routing/` and your automation configuration.
2. Copy `custom_components/kramer_av_routing/` from this release **over the existing integration directory**, not over `/config/` itself.
3. Restart Home Assistant. Existing device entries and routing entity unique IDs are retained.
4. The integration now also sets up the `binary_sensor` and `button` platforms. Look in **Settings → Devices & services → Kramer AV Routing → Devices** for new entities.
5. HDCP-mode controls and VP-558 audio EQ controls are **disabled in the entity registry by default** to prevent accidental disruption; open the device's entity list and enable only the ones you intend to test.
6. For the VP-444, continue using **UDP / port 50000**. The shared video selector remains one logical output, while `DISPLAY?` monitors the two physical HDMI output connectors independently.
7. Verify microphones and display controls while physically near the hardware. Preset recall changes multiple audio/video routes; do not test during a live presentation.
8. If features are missing, check debug logs for skipped read-only probes. A read-only query confirms an address/value but does not guarantee write permissions.

### Limitations

- No EDID configuration or automatic EDID overwrite. This requires per-model-safe commands and validation.
- Only *saved* presets discovered at setup appear as recall buttons. The integration does not create/delete/save presets; reload after editing saved presets on the device.
- No hardware validation for the new controls. Simulated tests and Python test stubs do not replace a Home Assistant runtime check.
- Protocol 3000 devices differ in command IDs/ranges; HDCP, EQ, and microphone options are restricted to the documented model profiles.
- The current v0.5.0 release was packaged locally and is not automatically uploaded to GitHub.

To run the local test suite:

```bash
python -m unittest discover -s tests -v
```
