"""Presentation labels for USB devices, using descriptors and optional host IDs."""

import re
import shutil
import subprocess
import time
from functools import lru_cache
from pathlib import Path

from .models import UsbDevice, UsbInterface
from .usb_classes import lookup as class_name
from .vendors import lookup as built_in_vendor

_USB_IDS_PATHS = (
    Path("/usr/share/misc/usb.ids"),
    Path("/usr/share/hwdata/usb.ids"),
    Path("/var/lib/usbutils/usb.ids"),
)
_LSUSB_LINE = re.compile(
    r"^Bus\s+(\d+)\s+Device\s+(\d+):\s+ID\s+([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\s*(.*)$"
)


def _parse_lsusb(output: str) -> dict[tuple[int, int, int, int], str]:
    records = {}
    for line in output.splitlines():
        if match := _LSUSB_LINE.match(line):
            bus, number, vendor, product, name = match.groups()
            records[int(bus), int(number), int(vendor, 16), int(product, 16)] = name.strip()
    return records


@lru_cache(maxsize=2)
def _lsusb_records(time_bucket: int) -> dict[tuple[int, int, int, int], str]:
    executable = shutil.which("lsusb")
    if executable is None:
        return {}
    try:
        result = subprocess.run(
            [executable], capture_output=True, text=True, check=False, timeout=2
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    return _parse_lsusb(result.stdout) if result.returncode == 0 else {}


def _lsusb_name(device: UsbDevice) -> str | None:
    # A fixture report must never be identified using unrelated host hardware.
    if not device.sysfs_path.startswith("/sys/bus/usb/devices/"):
        return None
    if any(
        value is None
        for value in (device.bus_number, device.device_number, device.vendor_id, device.product_id)
    ):
        return None
    return _lsusb_records(int(time.monotonic() * 2)).get(
        (device.bus_number, device.device_number, device.vendor_id, device.product_id)
    )


def _lsusb_parts(device: UsbDevice) -> tuple[str | None, str | None]:
    name = _lsusb_name(device)
    if not name:
        return None, None
    _, products = _database()
    database_product = products.get((device.vendor_id, device.product_id))
    for suffix in (database_product, device.product):
        if suffix and name.casefold().endswith(suffix.casefold()):
            vendor = name[: -len(suffix)].strip()
            if vendor:
                return vendor, name[-len(suffix) :]
    return None, name


def _read_usb_ids(path: Path) -> tuple[dict[int, str], dict[tuple[int, int], str]]:
    vendors: dict[int, str] = {}
    products: dict[tuple[int, int], str] = {}
    current_vendor: int | None = None
    try:
        with path.open(encoding="utf-8", errors="replace") as source:
            for line in source:
                if line.startswith("\t\t"):
                    continue
                if line.startswith("\t"):
                    token, _, label = line[1:].strip().partition("  ")
                    if current_vendor is not None and len(token) == 4 and label:
                        try:
                            products[current_vendor, int(token, 16)] = label.strip()
                        except ValueError:
                            pass
                else:
                    token, _, label = line.strip().partition("  ")
                    current_vendor = None
                    if len(token) == 4 and label:
                        try:
                            current_vendor = int(token, 16)
                            vendors[current_vendor] = label.strip()
                        except ValueError:
                            pass
    except OSError:
        return {}, {}
    return vendors, products


@lru_cache(maxsize=1)
def _database() -> tuple[dict[int, str], dict[tuple[int, int], str]]:
    for path in _USB_IDS_PATHS:
        if path.is_file():
            return _read_usb_ids(path)
    return {}, {}


def vendor_label(device: UsbDevice) -> str | None:
    if device.vendor_id is None:
        return device.manufacturer
    lsusb_vendor, _ = _lsusb_parts(device)
    vendors, _ = _database()
    return (
        lsusb_vendor
        or vendors.get(device.vendor_id)
        or built_in_vendor(device.vendor_id)
        or device.manufacturer
    )


def product_label(device: UsbDevice) -> str | None:
    if device.vendor_id is None or device.product_id is None:
        return None
    _, lsusb_product = _lsusb_parts(device)
    _, products = _database()
    return lsusb_product or products.get((device.vendor_id, device.product_id))


def display_name(device: UsbDevice) -> str:
    product = device.product
    database_product = product_label(device)
    if product and database_product and product.casefold() not in database_product.casefold():
        return f"{product} ({database_product})"
    return (
        product or database_product or device.manufacturer or vendor_label(device) or "USB device"
    )


def _interface_type(interface: UsbInterface) -> str | None:
    if interface.class_code == 3 and interface.subclass == 1:
        if interface.protocol == 1:
            return "Keyboard"
        if interface.protocol == 2:
            return "Mouse"
    if interface.class_code == 8:
        return "Mass Storage"
    if interface.class_code == 0xE0 and interface.subclass == 1:
        return "Bluetooth"
    return class_name(interface.class_code)


def device_type(device: UsbDevice) -> str | None:
    if device.is_root_hub:
        return "USB root hub"
    types = tuple(
        dict.fromkeys(
            label for interface in device.interfaces if (label := _interface_type(interface))
        )
    )
    if types:
        return ", ".join(types)
    return class_name(device.class_code)
