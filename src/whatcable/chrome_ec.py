"""Read-only Chrome EC USB-PD information source."""

import fcntl
import struct
from pathlib import Path
from types import MappingProxyType

from .models import AdvancedDevice

_HEADER = struct.Struct("=IIIII")
_RESPONSE = struct.Struct("<BBBBHHHHI")
_POWER_INFO = 0x0103
_IOCTL = (3 << 30) | (_HEADER.size << 16) | (0xEC << 8)


def _port(port: int, device: Path) -> AdvancedDevice | None:
    response_size = _RESPONSE.size
    request = bytearray(_HEADER.size + response_size)
    _HEADER.pack_into(request, 0, 0, _POWER_INFO, 1, response_size, 0xFF)
    request[_HEADER.size] = port
    try:
        with device.open("rb", buffering=0) as handle:
            returned = fcntl.ioctl(handle.fileno(), _IOCTL, request, True)
    except (FileNotFoundError, PermissionError, OSError):
        return None
    _version, _command, _outsize, _insize, result = _HEADER.unpack_from(request)
    if result != 0 or returned < response_size:
        return None
    (
        role,
        charging_type,
        dual_role,
        _reserved,
        voltage_max,
        voltage_now,
        current_max,
        current_limit,
        max_power_uw,
    ) = _RESPONSE.unpack_from(request, _HEADER.size)
    properties = MappingProxyType(
        {
            "role": {0: "Disconnected", 1: "Source", 2: "Sink", 3: "Sink, not charging"}.get(
                role, f"Unknown ({role})"
            ),
            "charging_type": str(charging_type),
            "dual_role": "yes" if dual_role else "no",
            "voltage_now_mv": str(voltage_now),
            "voltage_max_mv": str(voltage_max),
            "current_limit_ma": str(current_limit),
            "current_max_ma": str(current_max),
            "max_power_mw": str(max_power_uw // 1000),
        }
    )
    return AdvancedDevice(
        "chrome_ec",
        f"port{port}",
        str(device),
        f"Chrome EC port {port}",
        None,
        None,
        None,
        f"{properties['role']} · {voltage_now / 1000:g} V",
        properties=properties,
    )


def enumerate_chrome_ec(
    device: Path = Path("/dev/cros_ec"), max_ports: int = 4
) -> tuple[AdvancedDevice, ...]:
    if not device.exists():
        return ()
    ports = []
    for index in range(max_ports):
        value = _port(index, device)
        if value is None:
            break
        ports.append(value)
    return tuple(ports)
