# Upgrade to v0.3.1-alpha

## VP-444 support

The VP-444 profile was added on top of the v0.3.0 VP profile framework. To upgrade from 0.3.0, replace the complete `/config/custom_components/kramer_av_routing` folder and restart Home Assistant. Version 0.2.0 users should also review the v0.3.0 changes in the README and changelog; the complete ZIP includes all features.

1. Back up the existing custom component and Home Assistant config.
2. For the VP-444, configure **UDP**, port **50000** (not TCP).
3. Use **Auto** routing family, **Auto** profile mode, **0** inputs and **0** outputs; alternatively specify **12** inputs and **1** logical output.
4. Confirm one source selector is created. Both HDMI output connectors share its selected input.
5. The system checks `ROUTE? 12,1` before permitting any switching; if this fails, confirm the device's model/firmware rather than forcing another model's profile.
6. The VP-444's layer 12 switches video and audio together. Verify physical operation before setting up automations.

**Not hardware-validated:** Tests use simulated Protocol 3000 endpoints. Full Home Assistant runtime/hassfest/HACS validation must still be performed.
