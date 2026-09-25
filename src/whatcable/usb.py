"""USB device discovery and topology from /sys/bus/usb/devices."""

from dataclasses import replace
from pathlib import Path

from .models import EMPTY_RAW, UsbDevice, UsbInterface
from .sysfs import SysfsRoots, attributes, iter_dirs, read_float, read_int, read_text


def _device_name_is_usb(name: str) -> bool:
    return name.startswith("usb") or ("-" in name and ":" not in name)


def _parent_key(key: str, known: set[str]) -> str | None:
    if key.startswith("usb"):
        return None
    candidate = key.rsplit(".", 1)[0] if "." in key else f"usb{key.split('-', 1)[0]}"
    return candidate if candidate in known else None


def _interfaces(device_path: Path, raw: bool) -> tuple[UsbInterface, ...]:
    result: list[UsbInterface] = []
    for entry in iter_dirs(device_path):
        if not entry.name.startswith(f"{device_path.name}:"):
            continue
        data = attributes(entry) if raw else EMPTY_RAW
        result.append(
            UsbInterface(
                sysfs_path=str(entry),
                number=read_text(entry / "bInterfaceNumber"),
                class_code=read_int(entry / "bInterfaceClass", 16),
                subclass=read_int(entry / "bInterfaceSubClass", 16),
                protocol=read_int(entry / "bInterfaceProtocol", 16),
                driver=(entry / "driver").resolve().name if (entry / "driver").exists() else None,
                raw=data,
            )
        )
    return tuple(result)


def enumerate_devices(roots: SysfsRoots, include_raw: bool = False) -> tuple[UsbDevice, ...]:
    paths = [path for path in iter_dirs(roots.usb_devices) if _device_name_is_usb(path.name)]
    known = {path.name for path in paths}
    devices: list[UsbDevice] = []
    for path in paths:
        key = path.name
        class_code = read_int(path / "bDeviceClass", 16)
        removable = read_text(path / "removable")
        parent = _parent_key(key, known)
        max_power = read_text(path / "bMaxPower")
        try:
            max_power_ma = int(max_power.removesuffix("mA")) if max_power else None
        except ValueError:
            max_power_ma = None
        devices.append(
            UsbDevice(
                sysfs_path=str(path),
                key=key,
                bus_number=read_int(path / "busnum"),
                device_number=read_int(path / "devnum"),
                devpath=read_text(path / "devpath"),
                parent_key=parent,
                child_keys=(),
                speed_mbps=read_float(path / "speed"),
                usb_version=read_text(path / "version"),
                vendor_id=read_int(path / "idVendor", 16),
                product_id=read_int(path / "idProduct", 16),
                manufacturer=read_text(path / "manufacturer"),
                product=read_text(path / "product"),
                serial=read_text(path / "serial"),
                class_code=class_code,
                subclass=read_int(path / "bDeviceSubClass", 16),
                protocol=read_int(path / "bDeviceProtocol", 16),
                max_power_ma=max_power_ma,
                configuration=read_text(path / "configuration"),
                driver=(path / "driver").resolve().name if (path / "driver").exists() else None,
                tx_lanes=read_int(path / "tx_lanes"),
                rx_lanes=read_int(path / "rx_lanes"),
                is_root_hub=key.startswith("usb"),
                is_hub=class_code == 9,
                is_internal=(removable == "fixed") if removable is not None else None,
                interfaces=_interfaces(path, include_raw),
                raw=attributes(path) if include_raw else EMPTY_RAW,
            )
        )
    children: dict[str, list[str]] = {device.key: [] for device in devices}
    for device in devices:
        if device.parent_key in children:
            children[device.parent_key].append(device.key)
    return tuple(
        replace(device, child_keys=tuple(sorted(children[device.key]))) for device in devices
    )
