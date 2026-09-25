"""Normalized cable information derived from e-marker identity."""

from .models import CableInfo, TypeCCable
from .pd_decoder import decode_cable_vdo, decode_identity
from .vendors import lookup as vendor_name


def cable_info(cable: TypeCCable | None) -> CableInfo | None:
    if cable is None:
        return None
    decoded = decode_cable_vdo(cable.identity, cable.cable_type) if cable.identity else None
    identity = decode_identity(cable.identity) if cable.identity else None
    return CableInfo(
        cable_type=cable.cable_type,
        active=decoded.active
        if decoded
        else (cable.cable_type == "active" if cable.cable_type else None),
        speed_gbps=decoded.speed_gbps if decoded else None,
        current_a=decoded.current_a if decoded else None,
        max_voltage_v=decoded.max_voltage_v if decoded else None,
        max_power_w=decoded.max_power_w if decoded else None,
        vendor_id=identity.vendor_id if identity else None,
        vendor_name=vendor_name(identity.vendor_id) if identity else None,
    )
