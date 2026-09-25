"""USB PD identity and cable-VDO decoding (derived from the PD specification)."""

from dataclasses import dataclass

from .models import Identity


@dataclass(frozen=True, slots=True)
class CableVdo:
    active: bool
    speed_gbps: int | None
    current_a: int | None
    max_voltage_v: int
    max_power_w: int | None


@dataclass(frozen=True, slots=True)
class DecodedIdentity:
    vendor_id: int | None
    product_id: int | None
    ufp_product_type: str | None
    modal_operation: bool | None


def decode_identity(identity: Identity) -> DecodedIdentity:
    header = identity.id_header
    if header is None:
        return DecodedIdentity(None, None, None, None)
    product_types = {
        1: "hub",
        2: "peripheral",
        3: "passive_cable",
        4: "active_cable",
        5: "ama",
        6: "vpd",
    }
    product_id = (identity.product or 0) & 0xFFFF if identity.product is not None else None
    return DecodedIdentity(
        vendor_id=header & 0xFFFF,
        product_id=product_id,
        ufp_product_type=product_types.get((header >> 27) & 0x7),
        modal_operation=bool((header >> 26) & 1),
    )


def decode_cable_vdo(identity: Identity, cable_type: str | None) -> CableVdo | None:
    vdo = identity.product_type_vdo1
    if vdo is None:
        return None
    active = cable_type == "active" or ((identity.id_header or 0) >> 27 & 0x7) == 4
    speed = {0: 0, 1: 5, 2: 10, 3: 40, 4: 80}.get(vdo & 0x7)
    current = {1: 3, 2: 5}.get((vdo >> 5) & 0x3)
    voltage = {0: 20, 1: 30, 2: 40, 3: 50}[(vdo >> 9) & 0x3]
    return CableVdo(active, speed, current, voltage, voltage * current if current else None)
