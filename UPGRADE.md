# Upgrade to v0.4.0-alpha

1. Back up `/config/custom_components/kramer_av_routing/` and your Home Assistant configuration.
2. Copy the whole `custom_components/kramer_av_routing` directory from the release ZIP over the existing directory (do not create an extra nesting level).
3. Restart Home Assistant. Existing device entries should remain; the integration will now forward the new `switch` and `number` platforms as well as `select`.
4. Open the Kramer device in **Settings → Devices & services**. If it reports supported functions, optional controls will appear. Commands rejected or unrecognized by the unit will be omitted.
5. For the **VP-444**, keep **UDP port 50000**. The existing routing selector remains; any advanced controls shown depend on read-only status responses from your firmware.
6. Test a low-risk control such as front-panel lock or audio mute manually before adding automations. Avoid testing standby or output resolution remotely without recovery access.
7. If controls are missing, enable debug logging for `custom_components.kramer_av_routing` and inspect the optional-control discovery logs. A failed optional query is not a routing failure.

**Compatibility:** Uses the existing `kramer_av_routing` domain and leaves routing unique IDs intact. Version 0.4.0 has been tested with simulation and Python stubs, not a real Home Assistant runtime. The new entities have their own unique IDs.

**Limits:** Generic 1-based mute/video-enable/freeze probing is a best-effort common-command feature, not a guarantee of correctness on every model. Volume ranges, scaler settings, EDID and HDCP often vary across devices and require additional verified profiles.
