# Kramer AV branding

The Home Assistant integration is **Kramer AV**.

Local integration assets for Home Assistant 2026.3+:

- `custom_components/kramer_av_routing/brand/icon.png` — 256×256 icon
- `custom_components/kramer_av_routing/brand/icon@2x.png` — 512×512 icon
- `custom_components/kramer_av_routing/brand/logo.png` — logo for light backgrounds
- `custom_components/kramer_av_routing/brand/dark_logo.png` — logo for dark backgrounds

The icon is based on the recognizable Kramer colored-loop mark, derived from a publicly distributed Kramer logo image. The accompanying wordmark was rendered with an available font, not supplied by Kramer. For exact reproduction, replace the included logo assets with manufacturer-provided artwork.
Kramer and its logo are trademarks of their respective owner. This project is
unofficial and independent.

The integration ID remains `kramer_av_routing`, even though the user-facing
name is now `Kramer AV`. You do not need to re-add devices to get the new name.
Restart Home Assistant after replacing the integration folder, and hard refresh
the browser if a previous icon is cached.
