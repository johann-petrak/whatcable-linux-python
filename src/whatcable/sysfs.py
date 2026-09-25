"""Defensive readers for Linux sysfs and fixture trees."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class SysfsRoots:
    """Sysfs locations; ``from_root`` expects a tree containing ``sys``."""

    usb_devices: Path = Path("/sys/bus/usb/devices")
    typec: Path = Path("/sys/class/typec")
    usb_power_delivery: Path = Path("/sys/class/usb_power_delivery")
    power_supply: Path = Path("/sys/class/power_supply")
    thunderbolt: Path = Path("/sys/bus/thunderbolt/devices")
    usb4: Path = Path("/sys/bus/usb4/devices")
    debugfs: Path = Path("/sys/kernel/debug")

    @classmethod
    def from_root(cls, root: Path) -> "SysfsRoots":
        sys = root / "sys"
        return cls(
            usb_devices=sys / "bus/usb/devices",
            typec=sys / "class/typec",
            usb_power_delivery=sys / "class/usb_power_delivery",
            power_supply=sys / "class/power_supply",
            thunderbolt=sys / "bus/thunderbolt/devices",
            usb4=sys / "bus/usb4/devices",
            debugfs=sys / "kernel/debug",
        )


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except (FileNotFoundError, NotADirectoryError, PermissionError, OSError):
        return None


def read_int(path: Path, base: int = 10) -> int | None:
    value = read_text(path)
    if value is None:
        return None
    try:
        return int(value, base)
    except ValueError:
        return None


def read_float(path: Path) -> float | None:
    value = read_text(path)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def read_bool(path: Path) -> bool | None:
    value = read_text(path)
    if value is None:
        return None
    if value.lower() in {"1", "yes", "true", "enabled"}:
        return True
    if value.lower() in {"0", "no", "false", "disabled"}:
        return False
    return None


def iter_dirs(path: Path) -> Iterator[Path]:
    try:
        yield from sorted(
            (entry for entry in path.iterdir() if entry.is_dir()), key=lambda p: p.name
        )
    except (FileNotFoundError, NotADirectoryError, PermissionError, OSError):
        return


def attributes(path: Path) -> Mapping[str, str]:
    values: dict[str, str] = {}
    try:
        entries = list(path.iterdir())
    except (FileNotFoundError, NotADirectoryError, PermissionError, OSError):
        return MappingProxyType(values)
    for entry in entries:
        if entry.is_file() and (value := read_text(entry)) is not None:
            values[entry.name] = value
    return MappingProxyType(values)
