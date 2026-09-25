# Installing WhatCable on Linux

WhatCable's command-line program needs Python 3.11 or newer. The optional GUI also
needs GTK4, libadwaita, and PyGObject supplied by your Linux distribution. The
commands below assume you have a copy of this repository and are in its
`whatcable-linux-python` directory (the one containing `pyproject.toml`). You do
not need to run WhatCable as root; kernel attributes that your account cannot read
will simply be unavailable.

## Install uv

[uv](https://docs.astral.sh/uv/getting-started/installation/) manages the Python
environment and installs this project. Install it using your distribution's package
manager if available, or follow the linked official uv installation instructions.
Then check that your shell can find it:

```bash
uv --version
```

If you have just installed uv and the command is not found, open a new terminal or
follow the installer's instructions for adding it to your `PATH`.

## Command-line installation

From the project directory, install the locked dependencies and the `whatcable`
command into a project-local `.venv`:

```bash
uv sync
uv run whatcable --help
uv run whatcable --all
```

The project requests Python 3.12 in `.python-version`; uv can obtain a compatible
Python automatically if necessary. `pyproject.toml` requires at least Python 3.11.
You do not have to activate `.venv` when using `uv run`. To wait for a new USB-C
cable connection, run `uv run whatcable --connect` before attaching it. See the
[command-line guide](cli.md) for the other options.

For optional USB device names from `lsusb`, install your distribution's `usbutils`
package. On Debian or Ubuntu:

```bash
sudo apt install usbutils
```

The CLI works without `lsusb`; it then uses available sysfs strings and the
optional local USB ID database.

## GUI installation

The GUI requires native packages that this project's Python dependencies do not
install. On Debian or Ubuntu:

```bash
sudo apt update
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
```

For other distributions, install their packages for Python GObject introspection,
GTK4, and libadwaita. Check that the distribution Python is version 3.11 or newer
(replace `/usr/bin/python3` below if your distribution uses another path):

```bash
/usr/bin/python3 --version
```

Then, from the project directory, create a virtual environment based on that
exact interpreter and make its system packages visible:

```bash
uv venv --python /usr/bin/python3 --system-site-packages .venv
uv sync --python /usr/bin/python3
uv run --python /usr/bin/python3 whatcable-gui
```

`uv venv` recreates an existing `.venv`, so preserve anything you installed there
separately before running it. This replaces the CLI environment with one using the
distribution Python; the CLI remains available through
`uv run --python /usr/bin/python3 whatcable`. Specify `--python /usr/bin/python3`
on later `uv run` or `uv sync` commands in this GUI setup, because the project's
`.python-version` otherwise requests Python 3.12. If your distribution Python is
older than 3.11, this GUI setup will not work with this project as-is.

To verify that the native libraries are visible before launching the GUI:

```bash
.venv/bin/python -c "import gi; gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1'); from gi.repository import Gtk, Adw; print('GTK and libadwaita available')"
```

If `whatcable-gui` reports that PyGObject, GTK4, or libadwaita is missing, check
the distribution packages, the interpreter used to create `.venv`, and whether
the environment was created with `--system-site-packages`. A Python downloaded
by uv normally cannot see the distribution's `gi` installation. See the
[GUI guide](gui.md) for the interface itself.

## Checking the result

`uv run whatcable --all` should show a `USB devices` section even if no Type-C
ports are exposed. Missing USB-C cable information is often a limitation of what
the host controller and kernel make available, not an installation failure. You
can run the project's tests with `uv run pytest -q` in a CLI environment, or with
`uv run --python /usr/bin/python3 pytest -q` in the GUI environment.
