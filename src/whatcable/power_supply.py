"""Read UCSI negotiated USB-C power contracts without confusing them with PDOs."""

import re
from pathlib import Path

from .models import PowerSupplyContract
from .sysfs import SysfsRoots, iter_dirs, read_int, read_text

_UCSI_NAME = re.compile(r"^ucsi-source-psy-.+:(\d+)$")


def _millis(path: Path, attribute: str) -> int | None:
    value = read_int(path / attribute)
    return value // 1000 if value is not None else None


def _contract(path: Path) -> PowerSupplyContract:
    online = read_text(path / "online")
    return PowerSupplyContract(
        sysfs_path=str(path),
        online=(online == "1") if online is not None else None,
        voltage_now_mv=_millis(path, "voltage_now"),
        current_now_ma=_millis(path, "current_now"),
        current_max_ma=_millis(path, "current_max"),
        voltage_min_mv=_millis(path, "voltage_min"),
        voltage_max_mv=_millis(path, "voltage_max"),
        charge_type=read_text(path / "charge_type"),
        usb_type=read_text(path / "usb_type"),
    )


def fallback_contract_for_port(roots: SysfsRoots, port_key: str) -> PowerSupplyContract | None:
    """Use UCSI's conventional 1-based port suffix only when it is unambiguous."""
    contract, _warning = fallback_contract_with_warning(roots, port_key)
    return contract


def fallback_contract_with_warning(
    roots: SysfsRoots, port_key: str
) -> tuple[PowerSupplyContract | None, str | None]:
    """Return a contract only for a unique fallback match, explaining ambiguity."""
    match = re.fullmatch(r"port(\d+)", port_key)
    if not match:
        return None, None
    suffix = int(match.group(1)) + 1
    candidates = [
        path
        for path in iter_dirs(roots.power_supply)
        if (name_match := _UCSI_NAME.match(path.name)) and int(name_match.group(1)) == suffix
    ]
    if len(candidates) == 1:
        return _contract(candidates[0]), None
    if len(candidates) > 1:
        return (
            None,
            f"{port_key}: {len(candidates)} UCSI power supplies match fallback suffix {suffix}",
        )
    return None, None
