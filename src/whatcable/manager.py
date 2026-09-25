"""Top-level scan orchestration."""

import re
from dataclasses import replace
from pathlib import Path

from .advanced import enumerate_thunderbolt
from .chrome_ec import enumerate_chrome_ec
from .models import Report
from .power_supply import fallback_contract_with_warning
from .sysfs import SysfsRoots
from .typec import enumerate_ports
from .usb import enumerate_devices


def scan(roots: SysfsRoots | None = None, *, include_raw: bool = False) -> Report:
    live_scan = roots is None
    roots = roots or SysfsRoots()
    ports = enumerate_ports(roots, include_raw)
    warnings = []
    enriched_ports = []
    for port in ports:
        contract, warning = fallback_contract_with_warning(roots, port.key)
        enriched_ports.append(replace(port, power_supply_contract=contract))
        if warning:
            warnings.append(warning)
    ports = tuple(enriched_ports)
    usb_devices = enumerate_devices(roots, include_raw)
    known_usb = {device.key for device in usb_devices}
    correlated_ports = []
    for port in ports:
        keys = []
        try:
            children = list(Path(port.sysfs_path).iterdir())
        except OSError:
            children = []
        for child in children:
            if match := re.fullmatch(r"usb(\d+)-port(\d+)", child.name):
                key = f"{match.group(1)}-{match.group(2)}"
                if key in known_usb:
                    keys.append(key)
        correlated_ports.append(replace(port, usb_device_keys=tuple(sorted(set(keys)))))
    ports = tuple(correlated_ports)
    return Report(
        schema_version=1,
        usb_devices=usb_devices,
        typec_ports=ports,
        advanced=enumerate_thunderbolt(roots, include_raw)
        + (enumerate_chrome_ec() if live_scan else ()),
        warnings=tuple(warnings),
    )
