# Changelog

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
