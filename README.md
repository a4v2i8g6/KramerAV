# Kramer AV Routing — Protocol 3000 for Home Assistant

**Version 0.1.0 — experimental prototype, not hardware-validated.**

A native custom integration for Kramer Protocol 3000 matrix and presentation switchers.
It can control independent video output routes using `ROUTE` or `VID` commands over
TCP or UDP, and keep Home Assistant in sync via status polling and received routing
notifications. It does **not** use Protocol 2000 or the `kessler-av` library.

## What works in this initial version

- Set up devices in Home Assistant's **Devices & services** UI, with connection verification via `MODEL?`.
- TCP (normally port **5000**) and UDP (normally port **50000**), with custom ports.
- Query the device model and Protocol 3000 version.
- Discover input/output counts using `INFO-IO?`, or enter manual counts if unsupported.
- Auto-detect common video routing query families: `ROUTE? 1,<output>` and `VID? <output>`, or override manually.
- Expose one `select` entity for every output: route Input 1/2/3/... independently.
- Receive routing notifications (`ROUTE`/`VID`) and poll status every 30 seconds by default.
- Reconnect after connection loss on the next poll.
- Name inputs and outputs, without changing their numeric physical addresses.
- VID devices have a **Disconnected** option (input 0).
- Works alongside `custom_components/kramer` from the original Protocol 2000 integration.

**Important compatibility caveat:** This is a *generic common-command* implementation, not
certified support for every Kramer VP, VS or MTX model. VP scalers, modular matrices,
and newer Extended Protocol 3000 products may have layer, destination, or signal-ID
semantics that differ from these two command families. Always verify the exact model's
command documentation before controlling equipment in production.

## Not yet implemented

- Extended `X-ROUTE` with typed signal/port IDs (`SIGNALS-LIST?` discovery)
- RS-232/USB-serial transport
- Separate audio routing / audio-follow-video
- Preset save/recall, EDID, video/scaler functions, hardware labels
- Multiple destinations with nonsequential IDs, modular chassis maps
- Authentication, TLS and automatic discovery of host IPs
- Per-model profiles or a runtime routing-command diagnostic UI

## Install manually on Home Assistant

1. Unzip the project package.
2. Copy the **entire** folder `custom_components/kramer_av_routing` into:

   `/config/custom_components/kramer_av_routing/`

3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration**, and search for
   **Kramer AV Routing (Protocol 3000)**.
5. Enter the host/IP, transport and port.
   - **TCP** typically uses port **5000**.
   - **UDP** typically uses port **50000**. Set the port to 50000 when choosing UDP.
6. Set input and output counts to `0` to try automatic detection with `INFO-IO?`.
   If it fails, remove the unfinished entry and add it with manual counts.
7. Leave routing family on **Auto**; if neither query works, check the model manual
   and choose **ROUTE** or **VID** explicitly on a fresh setup attempt.
8. Open the device in Home Assistant and find the new output `select` entities.

For each output, the source list contains labels such as `Input 1` and `Input 2`.
Options for custom labels are in the integration's **Configure** dialog.
`Input 1 — PC`, `Input 2 — Apple TV`, etc. are unique and preserve port order.

## Example automation action

```yaml
action: select.select_option
target:
  entity_id: select.kramer_vp_778_output_1
data:
  option: "Input 2"
```

The entity ID above is only an **example**. Copy the actual output entity ID from your device.

## Testing and troubleshooting

The integration initially performs **read-only queries** (no switching during setup).
A write command is sent only when you choose an input:

- `#ROUTE 1,3,2\r` routes video input 2 to output 3 (ROUTE family)
- `#VID 2>3\r` routes video input 2 to output 3 (VID family)

Queries are `#ROUTE? 1,3\r`, `#VID? 3\r`, `#MODEL?\r`, etc.

If **No supported video routing query** appears in logs, your device may require
Extended Protocol 3000 (`X-ROUTE`) or a different layer/channel format.
If **Unable to detect input/output count** appears, enter manual values.
Some Kramer VP units support only serial or UDP; TCP will not work for those models.

Enable debug logs in `configuration.yaml` while testing:

```yaml
logger:
  logs:
    custom_components.kramer_av_routing: debug
```

The local protocol tests require only Python 3.11+:

```bash
python -m unittest discover -s tests -v
```

This package is structured for future publication as a HACS custom GitHub repository,
**but is not itself published on GitHub or available in HACS**. Install manually until
it is hosted in a repository.

## Documentation references

- Kramer Protocol 3000 Reference Guide v3.0: https://k.kramerav.com/downloads/protocols/protocol_3000_3.0_master_user.pdf
- Existing Protocol 2000 integration (inspiration only, not bundled): https://github.com/krohrbaugh/kramer-homeassistant

## License

MIT. This prototype is independent and not affiliated with Kramer Electronics or the
original Protocol 2000 integration author.
