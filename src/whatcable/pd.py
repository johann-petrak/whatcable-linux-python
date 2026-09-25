"""Directory-based USB Power Delivery capability parsing."""

import re
from pathlib import Path

from .models import EMPTY_RAW, PdCapabilities, PowerDataObject
from .sysfs import SysfsRoots, attributes, iter_dirs, read_int, read_text

_PDO_FLAGS = (
    "dual_role_data",
    "dual_role_power",
    "usb_communication_capable",
    "usb_suspend_supported",
    "unconstrained_power",
    "pps_power_limited",
)


def _number(path: Path, name: str) -> int | None:
    """PDO sysfs attributes are expressed directly in mV, mA, and mW."""
    return read_int(path / name)


def _pdo(path: Path, include_raw: bool) -> PowerDataObject | None:
    index, separator, supply_type = path.name.partition(":")
    if not separator:
        return None
    try:
        position = int(index)
    except ValueError:
        return None
    fixed = supply_type == "fixed_supply"
    min_voltage = _number(path, "minimum_voltage") or (_number(path, "voltage") if fixed else None)
    max_voltage = _number(path, "maximum_voltage") or (_number(path, "voltage") if fixed else None)
    current = _number(path, "maximum_current") or _number(path, "operational_current")
    power = _number(path, "maximum_power") or _number(path, "operational_power")
    if power is None and max_voltage is not None and current is not None:
        power = max_voltage * current // 1000
    flags = {name: value for name in _PDO_FLAGS if (value := read_text(path / name)) is not None}
    return PowerDataObject(
        position=position,
        supply_type=supply_type,
        min_voltage_mv=min_voltage,
        max_voltage_mv=max_voltage,
        maximum_current_ma=current,
        maximum_power_mw=power,
        peak_current=read_text(path / "peak_current"),
        sysfs_path=str(path),
        raw=attributes(path) if include_raw else EMPTY_RAW,
        flags=flags,
    )


def _avp_pdos(path: Path, include_raw: bool) -> list[PowerDataObject]:
    """Adjustable supplies expose one current attribute for each voltage range."""
    index, _, supply_type = path.name.partition(":")
    if "adjustable_voltage_supply" not in supply_type:
        return []
    try:
        position = int(index)
    except ValueError:
        return []
    result = []
    for attribute in attributes(path):
        match = re.fullmatch(r"maximum_current_(\d+)V_to_(\d+)V", attribute)
        if not match or (current := _number(path, attribute)) is None:
            continue
        minimum, maximum = (int(value) * 1000 for value in match.groups())
        result.append(
            PowerDataObject(
                position,
                supply_type,
                minimum,
                maximum,
                current,
                maximum * current // 1000,
                read_text(path / "peak_current"),
                str(path),
                attributes(path) if include_raw else EMPTY_RAW,
                {
                    name: value
                    for name in _PDO_FLAGS
                    if (value := read_text(path / name)) is not None
                },
            )
        )
    return sorted(result, key=lambda pdo: (pdo.min_voltage_mv or 0, pdo.max_voltage_mv or 0))


def _raw_fixed_pdo(position: int, word: int, path: Path) -> PowerDataObject | None:
    if word < 0 or word >> 30:
        return None
    voltage_mv = ((word >> 10) & 0x3FF) * 50
    current_ma = (word & 0x3FF) * 10
    if not voltage_mv or not current_ma:
        return None
    return PowerDataObject(
        position,
        "fixed_supply",
        voltage_mv,
        voltage_mv,
        current_ma,
        voltage_mv * current_ma // 1000,
        None,
        str(path),
    )


def parse_capability_directory(
    path: Path,
    *,
    role: str,
    provenance: str,
    revision: str | None = None,
    version: str | None = None,
    include_raw: bool = False,
) -> PdCapabilities | None:
    pdos = []
    for entry in iter_dirs(path):
        avs = _avp_pdos(entry, include_raw)
        if avs:
            pdos.extend(avs)
        elif (pdo := _pdo(entry, include_raw)) is not None:
            pdos.append(pdo)
    if path.is_file():
        text = read_text(path) or ""
        for position, token in enumerate(text.replace(",", " ").split(), start=1):
            try:
                word = int(token, 0)
            except ValueError:
                try:
                    word = int(token, 16)
                except ValueError:
                    continue
            if (pdo := _raw_fixed_pdo(position, word, path)) is not None:
                pdos.append(pdo)
    if not pdos:
        return None
    return PdCapabilities(
        str(path),
        role,
        provenance,
        revision,
        version,
        tuple(sorted(pdos, key=lambda p: p.position)),
    )


def class_capabilities_for_port(
    roots: SysfsRoots, port_key: str, *, include_raw: bool = False
) -> tuple[PdCapabilities, ...]:
    """Fallback for PD class objects whose ``device`` link identifies the Type-C owner."""
    result: list[PdCapabilities] = []
    for pd in iter_dirs(roots.usb_power_delivery):
        try:
            ancestry = {part for part in (pd / "device").resolve().parts}
        except OSError:
            continue
        if f"{port_key}-partner" in ancestry:
            provenance = "partner-class"
        elif port_key in ancestry:
            provenance = "port-self"
        else:
            continue
        revision = read_text(pd / "revision")
        version = read_text(pd / "version")
        for directory, role in (("source-capabilities", "source"), ("sink-capabilities", "sink")):
            caps = parse_capability_directory(
                pd / directory,
                role=role,
                provenance=provenance,
                revision=revision,
                version=version,
                include_raw=include_raw,
            )
            if caps is not None:
                result.append(caps)
    return tuple(result)
