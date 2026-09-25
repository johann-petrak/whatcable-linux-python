"""Conservative cable/partner alternate-mode compatibility assessment."""

from enum import StrEnum

from .models import TypeCPort


class AltModeCompatibility(StrEnum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


def cable_altmode_compatibility(port: TypeCPort) -> AltModeCompatibility:
    if port.partner is None or not port.partner.alt_modes or port.plug is None:
        return AltModeCompatibility.UNKNOWN
    partner_svids = {mode.svid for mode in port.partner.alt_modes if mode.svid is not None}
    plug_svids = {mode.svid for mode in port.plug.alt_modes if mode.svid is not None}
    if not plug_svids:
        return AltModeCompatibility.UNKNOWN
    return AltModeCompatibility.YES if partner_svids & plug_svids else AltModeCompatibility.NO
