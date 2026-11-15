# Upgrade to v0.3.0-alpha (from v0.2.0)

1. Back up `/config/custom_components/kramer_av_routing/` and your Home Assistant configuration first.
2. Replace the **entire** `custom_components/kramer_av_routing` folder with the one in the new package. Include `profiles.py`.
3. Restart Home Assistant and inspect **Settings → Devices & services → Kramer AV Routing**.
4. For recognized VP-440, VP-440X, VP-558, or VP-778 models, use **Auto** command family, **Auto** profile mode, and input/output counts `0` or the documented counts.
5. Check the reported profile, input names and logical output counts. The VP-778 exposes two scaler channels, not four duplicated physical output connectors.
6. Verify current source state before switching. Try one harmless input change and confirm the actual display output before using automations.
7. If discovery rejects your device's documented command layout, **do not force the profile**. Confirm model and firmware/manual. Use Generic only if you understand its physical numbering.

Existing v0.2 config entries do not have `profile_mode`; this version defaults to Auto. Existing input/output custom labels remain in options. Auto-profile activation can change selector options (for example `Input 1` becomes `Input 1 — HDMI 1`); update any automations using the old text values. Existing X-ROUTE devices keep their earlier discovery behavior. The output entity unique IDs for the new ROUTE-based VP profiles retain the original logical output index IDs.

**The entire project is still experimental:** no physical Kramer VP/VS equipment or actual Home Assistant installation has been used to validate compatibility.
