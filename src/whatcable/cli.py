"""Command-line entry point."""

import argparse
import json
import re
import signal
import sys
import time
from collections.abc import Mapping
from pathlib import Path

from .altmode import cable_altmode_compatibility
from .device_info import device_type, display_name, vendor_label
from .diagnostic import assess_charging
from .manager import scan
from .monitor import events
from .serialize import dumps, to_dict
from .sysfs import SysfsRoots


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="whatcable", description="Inspect Linux USB and USB-C devices"
    )
    parser.add_argument("--json", action="store_true", help="emit schema-versioned JSON")
    parser.add_argument("--raw", action="store_true", help="include raw sysfs attributes")
    parser.add_argument("--all", action="store_true", help="include empty ports and root hubs")
    parser.add_argument(
        "-i",
        "--info",
        nargs="+",
        metavar="N[,N...]",
        help="show all known details for numbered items (spaces and commas accepted)",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="disable terminal colour (output is currently plain text)",
    )
    parser.add_argument(
        "--watch", action="store_true", help="refresh when relevant udev events arrive"
    )
    parser.add_argument(
        "-C",
        "--connect",
        action="store_true",
        help="wait for a new USB-C cable connection, show its details, and exit",
    )
    parser.add_argument("--sysfs-root", type=Path, help="fixture root containing sys/")
    parser.add_argument("--version", action="version", version="whatcable 0.1.0")
    return parser


def _catalog(report, include_all: bool) -> list[tuple[str, object]]:
    """The numbered items in the human report, in the same display order."""
    return (
        [
            ("typec", port)
            for port in report.typec_ports
            if include_all
            or port.partner is not None
            or (port.power_supply_contract and port.power_supply_contract.online)
        ]
        + [
            ("usb", device)
            for device in report.usb_devices
            if include_all or not device.is_root_hub
        ]
        + [("advanced", device) for device in report.advanced]
    )


def _info_numbers(values: list[str]) -> list[int]:
    numbers = []
    for token in re.split(r"[\s,]+", " ".join(values).strip()):
        if not token:
            continue
        if not token.isascii() or not token.isdecimal() or int(token) < 1:
            raise ValueError(f"invalid item number: {token!r}")
        number = int(token)
        if number not in numbers:
            numbers.append(number)
    if not numbers:
        raise ValueError("--info needs at least one positive item number")
    return numbers


def _selected_items(report, include_all: bool, numbers: list[int]) -> list[dict[str, object]]:
    catalog = _catalog(report, include_all)
    if not catalog:
        raise ValueError("this report has no numbered items")
    invalid = [number for number in numbers if number > len(catalog)]
    if invalid:
        raise ValueError(
            f"item number(s) {', '.join(map(str, invalid))} not in this report "
            f"(valid: 1-{len(catalog)}; use --all for hidden items)"
        )
    document = to_dict(report, include_raw=True)
    records = {
        id(record): data
        for group, data_group in (
            (report.typec_ports, document["typec_ports"]),
            (report.usb_devices, document["usb_devices"]),
            (report.advanced, document["advanced"]),
        )
        for record, data in zip(group, data_group, strict=True)
    }
    return [
        {
            "number": number,
            "kind": catalog[number - 1][0],
            "details": records[id(catalog[number - 1][1])],
        }
        for number in numbers
    ]


def _detail_value(item: object) -> str:
    if item is True:
        return "yes"
    if item is False:
        return "no"
    if isinstance(item, str) and (
        not item or any(ord(char) < 32 or 127 <= ord(char) < 160 for char in item)
    ):
        return json.dumps(item, ensure_ascii=True)
    return str(item)


def _detail_lines(
    value: Mapping[str, object], indent: str = "  ", *, raw_keys: bool = False
) -> list[str]:
    lines = []
    for key, item in value.items():
        if item is None or item == {} or item == []:
            continue
        label = key if raw_keys else key.replace("_", " ").capitalize()
        if isinstance(item, Mapping):
            lines.append(f"{indent}{label}:")
            lines.extend(_detail_lines(item, indent + "  ", raw_keys=raw_keys or key == "raw"))
        elif isinstance(item, list):
            lines.append(f"{indent}{label}:")
            for entry in item:
                if isinstance(entry, Mapping):
                    lines.append(f"{indent}  -")
                    lines.extend(_detail_lines(entry, indent + "    ", raw_keys=raw_keys))
                else:
                    lines.append(f"{indent}  - {_detail_value(entry)}")
        else:
            lines.append(f"{indent}{label}: {_detail_value(item)}")
    return lines


def _info_text(items: list[dict[str, object]]) -> str:
    sections = []
    for item in items:
        details = item["details"]
        label = {"typec": "USB-C port", "usb": "USB device", "advanced": "Advanced source"}[
            item["kind"]
        ]
        name = details["summary"]["headline"]
        sections.append(
            "\n".join(
                [
                    f"[{item['number']}] {label}: {_detail_value(name)}",
                    *_detail_lines(details),
                ]
            )
        )
    return "\n\n".join(sections)


def _new_connection(previous, current):
    """Find a newly visible cable or partner, ignoring connections in the baseline."""
    old_ports = {port.key: port for port in previous.typec_ports}
    for port in current.typec_ports:
        old = old_ports.get(port.key)
        if old is None:
            if port.cable is not None or port.partner is not None:
                return port
        elif (port.cable is not None and port.cable != old.cable) or (
            port.partner is not None and old.partner is None
        ):
            return port
    return None


def _connect(roots, *, json_output: bool) -> None:
    baseline = scan(roots)
    print("Waiting for a USB-C cable connection (Ctrl+C to cancel)...", file=sys.stderr, flush=True)
    while True:
        time.sleep(0.5)
        current = scan(roots)
        port = _new_connection(baseline, current)
        if port is None:
            baseline = current
            continue
        # Give the kernel a moment to publish identity attributes after the attach event.
        time.sleep(0.5)
        settled = scan(roots, include_raw=True)
        settled_port = next((item for item in settled.typec_ports if item.key == port.key), None)
        if settled_port is None or (settled_port.cable is None and settled_port.partner is None):
            baseline = settled
            continue
        current, port = settled, settled_port
        if port.cable is None or port.cable.identity is None:
            print(
                "Cable identity is not exposed by the kernel; showing available port details.",
                file=sys.stderr,
                flush=True,
            )
        number = next(
            number
            for number, (kind, item) in enumerate(_catalog(current, True), 1)
            if kind == "typec" and item.key == port.key
        )
        items = _selected_items(current, True, [number])
        output = (
            json.dumps(
                {"schema_version": current.schema_version, "items": items},
                indent=2,
                sort_keys=True,
            )
            if json_output
            else _info_text(items)
        )
        print(output, flush=True)
        return


def _text(report, include_all: bool, include_raw: bool = False) -> str:
    numbers = {
        id(item): number for number, (_, item) in enumerate(_catalog(report, include_all), 1)
    }
    lines = ["USB-C ports"]
    visible_ports = 0
    if report.typec_ports:
        for port in report.typec_ports:
            if (
                not include_all
                and port.partner is None
                and not (port.power_supply_contract and port.power_supply_contract.online)
            ):
                continue
            partner = "connected" if port.partner else "empty"
            mode = f" — {port.power_operation_mode}" if port.power_operation_mode else ""
            lines.append(f"- [{numbers[id(port)]}] {port.key}: {partner}{mode}")
            visible_ports += 1
            if port.power_supply_contract and port.power_supply_contract.online:
                contract = port.power_supply_contract
                if contract.voltage_now_mv is not None and contract.current_now_ma is not None:
                    watts = contract.voltage_now_mv * contract.current_now_ma / 1_000_000
                    lines.append(f"  Negotiated power: {watts:g} W")
            lines.append(f"  Charging assessment: {assess_charging(port).summary}")
            if port.cable_info:
                cable = port.cable_info
                detail = cable.cable_type or "identified cable"
                if cable.speed_gbps:
                    detail += f", up to {cable.speed_gbps} Gbps"
                if cable.current_a:
                    detail += f", {cable.current_a} A"
                lines.append(f"  Cable: {detail}")
            compatibility = cable_altmode_compatibility(port)
            if compatibility != "unknown":
                lines.append(f"  Cable alternate-mode compatibility: {compatibility}")
            if include_raw and port.raw:
                lines.append(
                    "  Raw: "
                    + ", ".join(
                        f"{key}={_detail_value(value)}" for key, value in sorted(port.raw.items())
                    )
                )
            for capability in port.pd_capabilities:
                if capability.role != "source":
                    continue
                heading = (
                    "Partner offer"
                    if capability.provenance.startswith("partner")
                    else "This port advertises"
                )
                profiles = ", ".join(
                    f"{pdo.supply_type}: {pdo.max_voltage_mv / 1000:g} V"
                    + (f" @ {pdo.maximum_current_ma / 1000:g} A" if pdo.maximum_current_ma else "")
                    for pdo in capability.pdos
                    if pdo.max_voltage_mv is not None
                )
                if profiles:
                    lines.append(f"  {heading}: {profiles}")
                if include_raw and capability.pdos:
                    for pdo in capability.pdos:
                        if pdo.raw:
                            lines.append(
                                f"  PDO {pdo.position} raw: "
                                + ", ".join(
                                    f"{key}={_detail_value(value)}"
                                    for key, value in sorted(pdo.raw.items())
                                )
                            )
    else:
        lines.append("(no USB-C ports exposed by sysfs)")
    if report.typec_ports and not visible_ports:
        lines.append("(no visible USB-C ports; use --all to include empty ports)")
    lines.append("USB devices")
    devices = {device.key: device for device in report.usb_devices}
    visible_devices = 0
    for device in report.usb_devices:
        if not include_all and device.is_root_hub:
            continue
        depth = 0
        parent = device.parent_key
        while parent and parent in devices:
            depth += 1
            parent = devices[parent].parent_key
        label = display_name(device)
        ids = ""
        if device.vendor_id is not None and device.product_id is not None:
            ids = f" [{device.vendor_id:04x}:{device.product_id:04x}]"
        speed = f" — {device.speed_mbps:g} Mb/s" if device.speed_mbps is not None else ""
        lines.append(f"{'  ' * depth}- [{numbers[id(device)]}] {label}{ids}{speed}")
        visible_devices += 1
        kind = device_type(device)
        vendor = vendor_label(device)
        details = [
            item
            for item in (
                f"Type: {kind}" if kind else None,
                f"Vendor: {vendor}" if vendor else None,
            )
            if item
        ]
        if details:
            lines.append(f"{'  ' * (depth + 1)}" + "; ".join(details))
        if include_raw and device.raw:
            lines.append(
                f"{'  ' * (depth + 1)}Raw: "
                + ", ".join(
                    f"{key}={_detail_value(value)}" for key, value in sorted(device.raw.items())
                )
            )
    if not visible_devices:
        lines.append("(no USB devices exposed by sysfs)")
    elif not include_all:
        hidden = len(report.usb_devices) - visible_devices
        if hidden:
            lines.append(
                f"({visible_devices} USB devices shown; {hidden} root hubs hidden; use --all)"
            )
    if report.advanced:
        lines.append("Advanced sources")
        for device in report.advanced:
            lines.append(
                f"- [{numbers[id(device)]}] {device.name or device.key}: "
                f"{device.summary or device.source}"
            )
            if include_raw and device.raw:
                lines.append(
                    "  Raw: "
                    + ", ".join(
                        f"{key}={_detail_value(value)}" for key, value in sorted(device.raw.items())
                    )
                )
    if report.warnings:
        lines.append("Warnings")
        lines.extend(f"- {warning}" for warning in report.warnings)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.info and args.watch:
        parser.error("--info cannot be combined with --watch; item numbers can change on refresh")
    if args.connect and (args.info or args.watch):
        parser.error("--connect cannot be combined with --info or --watch")
    try:
        selected_numbers = _info_numbers(args.info) if args.info else None
    except ValueError as error:
        parser.error(str(error))
    roots = SysfsRoots.from_root(args.sysfs_root) if args.sysfs_root else None

    if args.connect:
        try:
            _connect(roots, json_output=args.json)
        except KeyboardInterrupt:
            return
        return

    def emit() -> None:
        report = scan(roots, include_raw=args.raw or selected_numbers is not None)
        if selected_numbers is not None:
            try:
                items = _selected_items(report, args.all, selected_numbers)
            except ValueError as error:
                parser.error(str(error))
            output = (
                json.dumps(
                    {"schema_version": report.schema_version, "items": items},
                    indent=2,
                    sort_keys=True,
                )
                if args.json
                else _info_text(items)
            )
        elif args.json:
            output = (
                json.dumps(
                    to_dict(report, include_raw=args.raw), sort_keys=True, separators=(",", ":")
                )
                if args.watch
                else dumps(report, include_raw=args.raw)
            )
        else:
            output = _text(report, args.all, args.raw)
        print(output, flush=True)

    emit()
    if args.watch:

        def stop(_signum, _frame) -> None:
            raise KeyboardInterrupt

        previous_term = signal.signal(signal.SIGTERM, stop)
        try:
            for _ in events():
                emit()
        except KeyboardInterrupt:
            return
        finally:
            signal.signal(signal.SIGTERM, previous_term)
