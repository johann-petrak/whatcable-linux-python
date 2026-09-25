"""Optional read-only Thunderbolt/USB4 sysfs discovery."""

from .models import EMPTY_RAW, AdvancedDevice
from .sysfs import SysfsRoots, attributes, iter_dirs, read_text

_BUS_FIELDS = (
    "authorized",
    "device_name",
    "device_type",
    "generation",
    "rx_lanes",
    "rx_speed",
    "security",
    "tx_lanes",
    "tx_speed",
    "unique_id",
    "vendor_name",
)


def _enumerate_bus(source: str, root, include_raw: bool) -> tuple[AdvancedDevice, ...]:
    devices = []
    for path in iter_dirs(root):
        values = {
            field: value for field in _BUS_FIELDS if (value := read_text(path / field)) is not None
        }
        if not values:
            continue
        name = values.get("device_name") or values.get("vendor_name") or path.name
        summary = (
            ", ".join(
                part
                for part in (
                    f"Gen {values['generation']}" if "generation" in values else None,
                    f"TX {values['tx_speed']} / RX {values['rx_speed']}"
                    if "tx_speed" in values or "rx_speed" in values
                    else None,
                )
                if part
            )
            or None
        )
        devices.append(
            AdvancedDevice(
                source=source,
                key=path.name,
                sysfs_path=str(path),
                name=name,
                vendor_name=values.get("vendor_name"),
                device_name=values.get("device_name"),
                unique_id=values.get("unique_id"),
                summary=summary,
                properties=values,
                raw=attributes(path) if include_raw else EMPTY_RAW,
            )
        )
    return tuple(devices)


def enumerate_thunderbolt(
    roots: SysfsRoots, include_raw: bool = False
) -> tuple[AdvancedDevice, ...]:
    return (
        _enumerate_bus("thunderbolt", roots.thunderbolt, include_raw)
        + _enumerate_bus("usb4", roots.usb4, include_raw)
        + _enumerate_debug_usb(roots.debugfs / "usb" / "devices", include_raw)
    )


def _enumerate_debug_usb(path, include_raw: bool) -> tuple[AdvancedDevice, ...]:
    text = read_text(path)
    if not text:
        return ()
    records: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith("T:"):
            if current:
                records.append(current)
            current = {"topology": line[2:].strip()}
        elif line.startswith("S:"):
            key, separator, value = line[2:].strip().partition("=")
            if separator and key:
                current[key.lower()] = value
    if current:
        records.append(current)
    return tuple(
        AdvancedDevice(
            source="usb_debugfs",
            key=f"debug-usb-{index}",
            sysfs_path=str(path),
            name=record.get("product") or record.get("manufacturer") or f"debug-usb-{index}",
            vendor_name=record.get("manufacturer"),
            device_name=record.get("product"),
            unique_id=None,
            summary=record.get("topology"),
            properties=record,
            raw=record if include_raw else EMPTY_RAW,
        )
        for index, record in enumerate(records)
    )
