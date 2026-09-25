"""Immutable normalized report values.

Links between records are paths or stable keys, never Python object references.  This
keeps reports straightforward to serialize and safe to use while hardware changes.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

EMPTY_RAW: Mapping[str, str] = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class UsbInterface:
    sysfs_path: str
    number: str | None
    class_code: int | None
    subclass: int | None
    protocol: int | None
    driver: str | None
    raw: Mapping[str, str] = field(default=EMPTY_RAW, repr=False)


@dataclass(frozen=True, slots=True)
class UsbDevice:
    sysfs_path: str
    key: str
    bus_number: int | None
    device_number: int | None
    devpath: str | None
    parent_key: str | None
    child_keys: tuple[str, ...]
    speed_mbps: float | None
    usb_version: str | None
    vendor_id: int | None
    product_id: int | None
    manufacturer: str | None
    product: str | None
    serial: str | None
    class_code: int | None
    subclass: int | None
    protocol: int | None
    max_power_ma: int | None
    configuration: str | None
    driver: str | None
    tx_lanes: int | None
    rx_lanes: int | None
    is_root_hub: bool
    is_hub: bool
    is_internal: bool | None
    interfaces: tuple[UsbInterface, ...] = ()
    raw: Mapping[str, str] = field(default=EMPTY_RAW, repr=False)


@dataclass(frozen=True, slots=True)
class Identity:
    id_header: int | None
    cert_stat: int | None
    product: int | None
    product_type_vdo1: int | None
    product_type_vdo2: int | None
    product_type_vdo3: int | None
    sysfs_path: str | None = None
    raw: Mapping[str, str] = field(default=EMPTY_RAW, repr=False)


@dataclass(frozen=True, slots=True)
class PowerDataObject:
    position: int
    supply_type: str
    min_voltage_mv: int | None
    max_voltage_mv: int | None
    maximum_current_ma: int | None
    maximum_power_mw: int | None
    peak_current: str | None
    sysfs_path: str
    raw: Mapping[str, str] = field(default=EMPTY_RAW, repr=False)
    flags: Mapping[str, str] = field(default=EMPTY_RAW, repr=False)


@dataclass(frozen=True, slots=True)
class PdCapabilities:
    sysfs_path: str
    role: str
    provenance: str
    revision: str | None
    version: str | None
    pdos: tuple[PowerDataObject, ...]


@dataclass(frozen=True, slots=True)
class PowerSupplyContract:
    sysfs_path: str
    online: bool | None
    voltage_now_mv: int | None
    current_now_ma: int | None
    current_max_ma: int | None
    voltage_min_mv: int | None
    voltage_max_mv: int | None
    charge_type: str | None
    usb_type: str | None


@dataclass(frozen=True, slots=True)
class AltMode:
    sysfs_path: str
    svid: int | None
    mode: int | None
    vdo: int | None
    active: bool | None


@dataclass(frozen=True, slots=True)
class TypeCPartner:
    sysfs_path: str
    accessory_mode: str | None
    supports_usb_power_delivery: bool | None
    pd_revision: str | None
    identity: Identity | None
    alt_modes: tuple[AltMode, ...] = ()
    raw: Mapping[str, str] = field(default=EMPTY_RAW, repr=False)


@dataclass(frozen=True, slots=True)
class TypeCCable:
    sysfs_path: str
    cable_type: str | None
    identity: Identity | None


@dataclass(frozen=True, slots=True)
class TypeCPlug:
    sysfs_path: str
    identity: Identity | None
    alt_modes: tuple[AltMode, ...]


@dataclass(frozen=True, slots=True)
class CableInfo:
    cable_type: str | None
    active: bool | None
    speed_gbps: int | None
    current_a: int | None
    max_voltage_v: int | None
    max_power_w: int | None
    vendor_id: int | None
    vendor_name: str | None


@dataclass(frozen=True, slots=True)
class AdvancedDevice:
    source: str
    key: str
    sysfs_path: str
    name: str | None
    vendor_name: str | None
    device_name: str | None
    unique_id: str | None
    summary: str | None = None
    properties: Mapping[str, str] = field(default=EMPTY_RAW, repr=False)
    raw: Mapping[str, str] = field(default=EMPTY_RAW, repr=False)


@dataclass(frozen=True, slots=True)
class TypeCPort:
    sysfs_path: str
    key: str
    data_role: str | None
    power_role: str | None
    power_operation_mode: str | None
    usb_capability: str | None
    typec_revision: str | None
    pd_revision: str | None
    partner: TypeCPartner | None
    cable: TypeCCable | None = None
    plug: TypeCPlug | None = None
    cable_info: CableInfo | None = None
    pd_capabilities: tuple[PdCapabilities, ...] = ()
    power_supply_contract: PowerSupplyContract | None = None
    usb_device_keys: tuple[str, ...] = ()
    raw: Mapping[str, str] = field(default=EMPTY_RAW, repr=False)


@dataclass(frozen=True, slots=True)
class Report:
    schema_version: int
    usb_devices: tuple[UsbDevice, ...]
    typec_ports: tuple[TypeCPort, ...] = ()
    advanced: tuple[AdvancedDevice, ...] = ()
    warnings: tuple[str, ...] = ()
