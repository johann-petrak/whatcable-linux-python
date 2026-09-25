# WhatCable for Linux

Inspect USB and USB-C information exposed by Linux sysfs.
If installed, `lsusb` supplies additional names for matching USB devices.

Guides: [installation](docs/installation.md), [command line](docs/cli.md),
[GUI](docs/gui.md), and [terms and device identification](docs/terms.md).

```bash
uv run whatcable
uv run whatcable --connect
uv run whatcable --info 2
uv run whatcable --json
uv run whatcable --watch
```

The CLI works with Python and `pyudev`. `whatcable-gui` additionally requires the
distribution's PyGObject, GTK4, libadwaita, and GObject-introspection packages.
See the [installation guide](docs/installation.md) for the separate CLI and GUI
setup steps, including how to use `uv` with the distribution's Python.

For reproducible inspection and tests, `--sysfs-root DIR` expects a fixture tree with
paths below `DIR/sys`, mirroring Linux sysfs. Missing or inaccessible kernel entries
are treated as ordinary incomplete data rather than errors.

The JSON output has `schema_version: 1`. Advertised PD profiles, port-self
capabilities, and negotiated UCSI power are reported separately.

## Source repositories and licenses

This Python port is licensed under [GPL-3.0-or-later](LICENSE); see also
[NOTICE](NOTICE). The following repositories informed its design or implementation:

| Repository | Relationship to this port | License |
| --- | --- | --- |
| [Zetaphor/whatcable-linux](https://github.com/Zetaphor/whatcable-linux) | Main Linux C++/Qt reference for USB topology, PD decoding, summaries, and selected vendor/class lookup data. | [MIT](https://github.com/Zetaphor/whatcable-linux/blob/main/LICENSE) |
| [vzaliva/whatcable-linux-cli](https://github.com/vzaliva/whatcable-linux-cli) | Fork of Zetaphor's port; reference for live UCSI power-supply information. | [MIT](https://github.com/vzaliva/whatcable-linux-cli/blob/main/LICENSE) |
| [nedrichards/whatcable-linux](https://github.com/nedrichards/whatcable-linux) | Python/GTK reference for sysfs PDO parsing, Type-C identities, cable plug data, optional sources, and UI patterns. | [GPL-3.0-or-later](https://github.com/nedrichards/whatcable-linux/blob/main/README.md#license) ([license text](https://github.com/nedrichards/whatcable-linux/blob/main/COPYING)) |
| [bjuergens/whatcable-gnome](https://github.com/bjuergens/whatcable-gnome) | Reference for kernel ABI observations and bug fixes; no code was copied from its GNOME extension. | [AGPL-3.0](https://github.com/bjuergens/whatcable-gnome/blob/main/LICENSE) |

The additional upstream repository in this lineage is
[darrylmorley/whatcable](https://github.com/darrylmorley/whatcable), the original
macOS app. Zetaphor's port derives from it, vzaliva forks Zetaphor, the GNOME
port cites both, and the nedrichards port cites the original independently. Its
[repository license](https://github.com/darrylmorley/whatcable/blob/main/LICENSE)
sets MIT as the default for public source files but identifies separately
licensed subdirectories, including proprietary plugin code. This port uses no
such plugin code.

The original app's
[third-party notices](https://github.com/darrylmorley/whatcable/blob/main/THIRD_PARTY_NOTICES.md)
also credit [edid-decode in v4l-utils](https://github.com/gjasny/v4l-utils/tree/master/utils/edid-decode)
for display-timing code under the
[MIT license](https://github.com/gjasny/v4l-utils/blob/master/utils/edid-decode/LICENSE).
That is an indirect upstream reference only; this Python port does not use its
EDID code. Separately, this port may run the installed `lsusb` program from
[usbutils](https://github.com/gregkh/usbutils) to improve device names;
[`lsusb.c` is GPL-2.0-or-later](https://github.com/gregkh/usbutils/blob/master/lsusb.c).
No usbutils source code is included here.
