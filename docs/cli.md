# Command-line guide

Run these commands from the project directory, or omit `uv run` if WhatCable is
installed in the active Python environment:

```bash
uv run whatcable
uv run whatcable -i 2
uv run whatcable --all
uv run whatcable --json
uv run whatcable --watch
```

The command reads Linux sysfs. It works without a USB-C controller or a connected
USB-C device; missing kernel data appears as an empty or incomplete section.

Each visible port, USB device, and advanced-source row has a number in square
brackets, such as `[2]`. Use that number without brackets to inspect everything
the program has collected for that item:

```bash
uv run whatcable --info 2
uv run whatcable -i 2 5,7
uv run whatcable --json --info 2,5
```

`-i` and `--info` accept positive numbers separated by spaces, commas, or both.
The detail view includes normalized fields, nested interfaces or PD capabilities,
and available raw sysfs attributes automatically. It omits fields for which the
kernel supplied no value; raw control characters and newlines are escaped in text
mode. With `--json`, `--info` returns a JSON object containing `schema_version`
and an `items` list with each selected number, kind, and details. An unknown number
produces an error. Numbers describe the current report and can change when hardware
changes. `--all` changes which rows are numbered, so use it both when listing and
when requesting a hidden root hub or empty port. `--info` cannot be combined with
`--watch` because a later scan could assign the same number to another device.

## Human-readable report

`USB-C ports` comes first. Each `portN` is a connector exposed by the Linux Type-C
class. `connected` means a partner device is present; `empty` means no partner was
found. The value after the dash, when present, is the kernel's power operation mode
(for example, `3.0A`). It is not a measurement of current flowing now. Empty ports
are hidden by default; use `--all` to show them.

Under a port you may see:

- `Negotiated power`: voltage multiplied by current reported by a matching UCSI
  power supply. This is distinct from a charger's advertised capabilities.
- `Charging assessment`: a cautious interpretation of the data the kernel exposes.
  An absence of negotiated data does **not** prove that no power is flowing.
- `Cable`: decoded e-marker or Type-C cable information, if available. A speed or
  current rating is a capability, not a measured transfer speed or current.
- `Cable alternate-mode compatibility`: whether the partner and cable plug expose a
  matching SVID. `yes` is only a limited compatibility check; it does not prove
  that a display or other alternate mode is currently working.
- `Partner offer`: source PDOs advertised by the connected partner, such as a
  charger. `This port advertises` describes the computer's own source PDOs. Neither
  line identifies the selected PDO.

`USB devices` follows. Each line is a device reported by the USB bus. Indentation
shows its position under a parent hub; a disk, mouse, or keyboard may therefore
appear below one or more hubs. The line shows the device's product string when
available, supplemented with a name from `lsusb` or the system USB ID database
where useful. The next line gives an inferred device type and a vendor name when
available. Type may be based on USB interface descriptors: for example, a disk can
say `Mass Storage`, and a boot-protocol input device can say `Keyboard` or `Mouse`.
A pair such as `[046d:c542]` is the hexadecimal vendor ID and product ID (VID:PID).
`Mb/s` is the reported USB link speed, not the device's actual transfer rate.
All scanned peripherals, including devices marked internal, are shown by default.
Root hubs are hidden; a count tells you how many were omitted and `--all` shows
them. This is why `lsusb` can list more rows than the default report.

`Advanced sources` lists optional Thunderbolt, USB4, Chrome EC, or USB debugfs
records when available. These may describe the same physical setup as a USB row;
they are separate kernel information sources, not necessarily extra devices.
`Warnings` explains ambiguous associations, such as multiple UCSI power supplies
that could match one Type-C port.

## Options

| Option | Effect |
| --- | --- |
| `--all` | Include empty Type-C ports and root hubs in text output and its item numbering. Internal USB devices are already shown. JSON includes all scanned records. |
| `-i N ...`, `--info N ...` | Show complete details for one or more numbered rows; separate numbers with spaces or commas. Raw attributes are included automatically. |
| `--json` | Emit the complete normalized report as JSON with `schema_version: 1`. |
| `--raw` | Include selected unprocessed sysfs attributes in text or the optional `raw` fields in JSON. |
| `--watch` | Print a report immediately, then print a fresh report after relevant USB, Type-C, PD, or power-supply events. With `--json`, each report is one JSON line. Stop with Ctrl+C. |
| `--no-color` | Keep terminal output uncolored; current text output is already plain. |
| `--sysfs-root DIR` | Read a test/fixture tree under `DIR/sys` instead of the host sysfs. |
| `--version` | Print the installed WhatCable version. |

JSON includes more identification fields than the text view: `manufacturer`,
`product`, `serial`, `vendor_id`, `product_id`, `class_code`, USB interface records,
drivers, topology keys, speeds, and the Type-C/PD records. A field can be `null` or
an interface list empty when the kernel does not expose it. `--raw` is useful when
checking the underlying attribute spelling and values; raw fields are kernel data
and may differ between machines.

If the `lsusb` command is installed, WhatCable uses its one-line names to
supplement the display labels for matching live devices. It matches bus number,
device number, and VID:PID, so an unrelated device is not given the wrong name.
When `lsusb` is absent, unreadable, or does not match, the optional system
`usb.ids` database and sysfs device strings provide fallbacks. A fixture selected
with `--sysfs-root` never uses host `lsusb` information.

See [GUI guide](gui.md) for the desktop view and [terms and device identification](terms.md)
for explanations of PDO, SVID, device classes, and what can identify peripherals.
