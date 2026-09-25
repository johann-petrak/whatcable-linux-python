"""Small presentation-independent summaries for CLI and GTK consumers."""

from dataclasses import dataclass

from .device_info import device_type, display_name, vendor_label
from .diagnostic import assess_charging
from .models import AdvancedDevice, TypeCPort, UsbDevice


@dataclass(frozen=True, slots=True)
class DeviceSummary:
    category: str
    status: str
    headline: str
    subtitle: str
    bullets: tuple[str, ...]
    icon_name: str


def summarize_port(port: TypeCPort) -> DeviceSummary:
    connected = port.partner is not None
    diagnostic = assess_charging(port)
    charging = bool(port.power_supply_contract and port.power_supply_contract.online)
    bullets = [f"Power role: {port.power_role}" if port.power_role else "Power role not exposed"]
    if port.pd_revision:
        bullets.append(f"USB PD revision: {port.pd_revision}")
    bullets.append(diagnostic.summary)
    return DeviceSummary(
        "typec",
        "charging" if charging else "connected" if connected else "empty",
        port.key,
        "Charging" if charging else "Partner connected" if connected else "No partner connected",
        tuple(bullets),
        "usb-symbolic",
    )


def summarize_usb(device: UsbDevice) -> DeviceSummary:
    name = display_name(device)
    vendor = vendor_label(device)
    kind = device_type(device)
    bullets = tuple(
        item
        for item in (
            f"Type: {kind}" if kind else None,
            f"Vendor: {vendor}" if vendor else None,
            f"Speed: {device.speed_mbps:g} Mb/s" if device.speed_mbps is not None else None,
            f"ID: {device.vendor_id:04x}:{device.product_id:04x}"
            if device.vendor_id is not None and device.product_id is not None
            else None,
        )
        if item
    )
    return DeviceSummary(
        "hub" if device.is_hub else "usb",
        "connected",
        name,
        f"{device.key} · {kind}" if kind else device.key,
        bullets,
        "network-workgroup-symbolic" if device.is_hub else "drive-removable-media-usb-symbolic",
    )


def summarize_advanced(device: AdvancedDevice) -> DeviceSummary:
    return DeviceSummary(
        "advanced",
        "connected",
        device.name or device.key,
        device.summary or device.source,
        (),
        "network-server-symbolic",
    )
