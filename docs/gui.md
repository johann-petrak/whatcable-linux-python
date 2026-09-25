# GUI guide

Start the desktop window from the project directory with:

```bash
uv run --python /usr/bin/python3 whatcable-gui
```

GTK4, libadwaita, and PyGObject must be visible to the Python environment. See the
[installation guide](installation.md) for Debian/Ubuntu setup and the correct `uv`
interpreter. The title shows the number of visible rows. Use the refresh button,
F5, or Ctrl+R to rescan. The window also
refreshes after relevant device events, with a short delay to combine bursts of
notifications.

## What the rows show

Rows appear in this order; there are no separate section headings in the current
window:

1. **USB-C ports:** one expandable row per visible Type-C connector. The subtitle
   says whether a partner is connected or whether an online UCSI charging contract
   is visible. The charging assessment appears inside the row. Expand it to read
   the available information. With **Show details**, the row also displays its
   power role and PD revision; partner and cable information; alternate modes; and
   advertised PDOs grouped as partner or port profiles. The profile limits are
   capabilities, not the selected charging profile. Raw port attributes appear
   when available.
2. **USB devices:** a product name from the device, supplemented by a matching
   `lsusb` or USB ID database name when useful. The subtitle contains the USB
   topology key (for example, `1-4.2`) and a broad function inferred from device
   or interface descriptors. With **Show details**, these rows become expandable
   and show the type, vendor, reported speed, VID:PID, and available raw sysfs
   attributes. A composite device can have several functions.
3. **Advanced sources:** optional Thunderbolt, USB4, Chrome EC, or debugfs entries.
   Expanding a row with **Show details** displays exposed properties such as vendor
   or device name, generation, and link information when that source supplies them.

If no rows pass the filters, the window shows a message suggesting filters or
kernel support. No Type-C row does not mean there are no USB devices; some systems
do not expose their ports through the Type-C class.

## Menu and display controls

The menu beside the refresh button contains four persistent settings:

- **Show hubs:** include external USB hubs. Root hubs are currently always hidden
  in the GUI.
- **Show empty ports:** include Type-C connectors without a detected partner.
- **Show internal devices:** include USB devices the kernel marks as fixed/internal.
  This is enabled by default; turning it off hides devices such as built-in cameras
  or Bluetooth adapters when the kernel marks them internal.
- **Show details:** show expandable USB details and additional port/advanced data,
  including available raw attributes. This can reveal serial numbers if supplied
  by a device.

Settings are saved in `$XDG_CONFIG_HOME/whatcable/settings.json`, or
`~/.config/whatcable/settings.json` when that environment variable is unset.
Port expansion is retained during a refresh while the window remains open.

The current GUI does not decode hard-disk capacity, filesystems, mouse buttons, or
keyboard layout. A USB class or interface can suggest a device's function, while
the product, manufacturer, VID:PID, and sometimes serial help identify its make
and model. See [terms and device identification](terms.md) for the limits of those
labels and the [CLI guide](cli.md) for JSON output with all normalized fields.
