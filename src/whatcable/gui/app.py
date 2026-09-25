"""Optional GTK4/libadwaita frontend."""

from pathlib import Path

from ..diagnostic import Bottleneck, assess_charging
from ..manager import scan
from ..monitor import create_monitor
from ..summary import summarize_advanced, summarize_port, summarize_usb
from .settings import load, save


def _pdo_range(pdo) -> str | None:
    """Format a profile's advertised voltage range without claiming selection."""
    if pdo.min_voltage_mv is None and pdo.max_voltage_mv is None:
        return None
    low = pdo.min_voltage_mv if pdo.min_voltage_mv is not None else pdo.max_voltage_mv
    high = pdo.max_voltage_mv if pdo.max_voltage_mv is not None else pdo.min_voltage_mv
    if low == high:
        return f"{low / 1000:g} V"
    return f"{low / 1000:g}–{high / 1000:g} V"


def _pdo_limit(pdo) -> str | None:
    if pdo.maximum_current_ma is not None:
        return f"up to {pdo.maximum_current_ma / 1000:g} A"
    if pdo.maximum_power_mw is not None:
        return f"up to {pdo.maximum_power_mw / 1000:g} W"
    return None


def main() -> None:
    try:
        import gi

        gi.require_version("Adw", "1")
        gi.require_version("Gtk", "4.0")
        from gi.repository import Adw, Gdk, Gio, GLib, Gtk
    except (ImportError, ValueError) as error:
        raise SystemExit(
            "whatcable-gui requires distribution PyGObject, GTK4, and libadwaita; "
            "create the uv environment with /usr/bin/python3 and --system-site-packages"
        ) from error

    class Application(Adw.Application):
        def __init__(self) -> None:
            super().__init__(
                application_id="io.github.johannpetrak.WhatCable",
                flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
            )
            self.window = None
            self.settings = load()
            self.refresh_source = 0
            self.monitor = None
            self.expanded_ports = set()

        def do_activate(self) -> None:
            if self.window is None:
                provider = Gtk.CssProvider()
                provider.load_from_path(str(Path(__file__).parents[1] / "data" / "style.css"))
                Gtk.StyleContext.add_provider_for_display(
                    Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
                self.window = Adw.ApplicationWindow(
                    application=self, title="WhatCable", default_width=720, default_height=600
                )
                self.listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
                toolbar = Adw.ToolbarView()
                header = Adw.HeaderBar()
                refresh = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Refresh")
                refresh.connect("clicked", lambda *_: self.refresh())
                header.pack_end(refresh)
                refresh_action = Gio.SimpleAction.new("refresh", None)
                refresh_action.connect("activate", lambda *_: self.refresh())
                self.add_action(refresh_action)
                self.set_accels_for_action("app.refresh", ["F5", "<Primary>r"])
                menu = Gio.Menu()
                for key, label, attribute in (
                    ("show-hubs", "Show hubs", "show_hubs"),
                    ("show-empty", "Show empty ports", "show_empty_ports"),
                    ("show-internal", "Show internal devices", "show_internal_devices"),
                    ("show-details", "Show details", "show_details"),
                ):
                    action = Gio.SimpleAction.new_stateful(
                        key,
                        None,
                        GLib.Variant.new_boolean(getattr(self.settings, attribute)),
                    )
                    action.connect("change-state", self._change_setting, attribute)
                    self.add_action(action)
                    menu.append(label, f"app.{key}")
                menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
                header.pack_end(menu_button)
                toolbar.add_top_bar(header)
                toolbar.set_content(Gtk.ScrolledWindow(child=self.listbox))
                self.window.set_content(toolbar)
                self._watch(GLib)
            self.refresh()
            self.window.present()

        def refresh(self) -> None:
            while (row := self.listbox.get_first_child()) is not None:
                self.listbox.remove(row)
            report = scan(include_raw=self.settings.show_details)
            visible = 0
            for port in report.typec_ports:
                summary = summarize_port(port)
                if summary.status == "empty" and not self.settings.show_empty_ports:
                    continue
                row = Adw.ExpanderRow(
                    title=summary.headline, subtitle=summary.subtitle, icon_name=summary.icon_name
                )
                row.set_expanded(port.key in self.expanded_ports)
                row.connect("notify::expanded", self._track_expansion, port.key)
                if self.settings.show_details:
                    for bullet in summary.bullets:
                        row.add_row(Adw.ActionRow(title=bullet))
                    self._add_port_details(row, port)
                diagnostic = assess_charging(port)
                banner = Adw.ActionRow(title=diagnostic.summary)
                banner.add_css_class(
                    "charging"
                    if diagnostic.status is Bottleneck.FINE
                    else "limit"
                    if diagnostic.status is Bottleneck.CABLE_LIMIT
                    else "neutral"
                )
                row.add_row(banner)
                self.listbox.append(row)
                visible += 1
            for device in report.usb_devices:
                if (
                    device.is_root_hub
                    or (device.is_hub and not self.settings.show_hubs)
                    or (device.is_internal and not self.settings.show_internal_devices)
                ):
                    continue
                summary = summarize_usb(device)
                if self.settings.show_details:
                    row = Adw.ExpanderRow(
                        title=summary.headline,
                        subtitle=summary.subtitle,
                        icon_name=summary.icon_name,
                    )
                    for bullet in summary.bullets:
                        row.add_row(Adw.ActionRow(title=bullet))
                    for key, value in sorted(device.raw.items()):
                        row.add_row(
                            Adw.ActionRow(title=key.replace("_", " ").title(), subtitle=value)
                        )
                    self.listbox.append(row)
                else:
                    self.listbox.append(
                        Adw.ActionRow(
                            title=summary.headline,
                            subtitle=summary.subtitle,
                            icon_name=summary.icon_name,
                        )
                    )
                visible += 1
            for device in report.advanced:
                summary = summarize_advanced(device)
                row = Adw.ExpanderRow(
                    title=summary.headline, subtitle=summary.subtitle, icon_name=summary.icon_name
                )
                if self.settings.show_details:
                    for key, value in sorted(device.properties.items()):
                        row.add_row(
                            Adw.ActionRow(title=key.replace("_", " ").title(), subtitle=value)
                        )
                    for key, value in sorted(device.raw.items()):
                        if key not in device.properties:
                            row.add_row(
                                Adw.ActionRow(title=key.replace("_", " ").title(), subtitle=value)
                            )
                self.listbox.append(row)
                visible += 1
            if not visible:
                self.listbox.append(
                    Adw.ActionRow(
                        title="No visible USB or USB-C devices",
                        subtitle="Enable filters or check kernel support.",
                    )
                )
            self.window.set_title(f"WhatCable — {visible} devices")

        def _add_port_details(self, row, port) -> None:
            """Append only evidence exposed by sysfs; never infer an active PDO."""
            if port.partner:
                title = "Partner"
                if port.partner.accessory_mode:
                    title += f" ({port.partner.accessory_mode})"
                subtitle = (
                    "USB PD supported"
                    if port.partner.supports_usb_power_delivery
                    else "USB PD support not exposed"
                )
                row.add_row(Adw.ActionRow(title=title, subtitle=subtitle))
                for mode in port.partner.alt_modes:
                    mode_label = (
                        f"SVID {mode.svid:04x}" if mode.svid is not None else "Alternate mode"
                    )
                    if mode.mode is not None:
                        mode_label += f", mode {mode.mode}"
                    row.add_row(Adw.ActionRow(title="Partner alternate mode", subtitle=mode_label))
            if port.cable_info:
                cable = port.cable_info
                details = []
                if cable.speed_gbps:
                    details.append(f"up to {cable.speed_gbps} Gb/s")
                if cable.current_a:
                    details.append(f"{cable.current_a} A")
                if cable.max_voltage_v:
                    details.append(f"{cable.max_voltage_v} V")
                if cable.vendor_name:
                    details.append(cable.vendor_name)
                row.add_row(
                    Adw.ActionRow(
                        title=(cable.cable_type or "Cable").capitalize(),
                        subtitle=", ".join(details) or "No e-marker rating exposed",
                    )
                )
            for capability in port.pd_capabilities:
                heading = (
                    "Partner PD profiles"
                    if capability.provenance.startswith("partner")
                    else "Port PD profiles"
                )
                source = capability.version or capability.revision or capability.provenance
                group = Adw.ExpanderRow(title=heading, subtitle=source)
                for pdo in capability.pdos:
                    range_text = _pdo_range(pdo)
                    limit = _pdo_limit(pdo)
                    group.add_row(
                        Adw.ActionRow(
                            title=f"PDO {pdo.position}: {pdo.supply_type}",
                            subtitle=" · ".join(item for item in (range_text, limit) if item),
                        )
                    )
                row.add_row(group)
            if port.plug and port.plug.alt_modes:
                for mode in port.plug.alt_modes:
                    mode_label = (
                        f"SVID {mode.svid:04x}" if mode.svid is not None else "Alternate mode"
                    )
                    row.add_row(
                        Adw.ActionRow(title="Cable plug alternate mode", subtitle=mode_label)
                    )
            for key, value in sorted(port.raw.items()):
                row.add_row(Adw.ActionRow(title=key.replace("_", " ").title(), subtitle=value))

        def _change_setting(self, action, value, attribute) -> None:
            setattr(self.settings, attribute, value.get_boolean())
            action.set_state(value)
            save(self.settings)
            self.refresh()

        def _track_expansion(self, row, _property, key) -> None:
            if row.get_expanded():
                self.expanded_ports.add(key)
            else:
                self.expanded_ports.discard(key)

        def _watch(self, glib) -> None:
            try:
                self.monitor = create_monitor()
                glib.io_add_watch(self.monitor.fileno(), glib.IO_IN, self._udev_event, glib)
            except OSError:
                self.monitor = None

        def _udev_event(self, _fd, _condition, glib) -> bool:
            if self.monitor is not None:
                self.monitor.poll(timeout=0)
            if self.refresh_source:
                glib.source_remove(self.refresh_source)
            self.refresh_source = glib.timeout_add(500, self._debounced_refresh)
            return True

        def _debounced_refresh(self) -> bool:
            self.refresh_source = 0
            self.refresh()
            return False

    Application().run(None)
