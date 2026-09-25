"""Conservative charging assessments based only on exposed evidence."""

from dataclasses import dataclass
from enum import StrEnum

from .models import TypeCPort


@dataclass(frozen=True, slots=True)
class ChargingDiagnostic:
    status: str
    summary: str
    inferred: bool


class Bottleneck(StrEnum):
    NO_CHARGER = "no_charger"
    CHARGER_LIMIT = "charger_limit"
    CABLE_LIMIT = "cable_limit"
    DEVICE_LIMIT = "device_limit"
    FINE = "fine"
    UNKNOWN = "unknown"


def assess_charging(port: TypeCPort) -> ChargingDiagnostic:
    contract = port.power_supply_contract
    partner_sources = [
        item
        for item in port.pd_capabilities
        if item.provenance.startswith("partner") and item.role == "source"
    ]
    if contract and contract.online and contract.voltage_now_mv and contract.current_now_ma:
        watts = contract.voltage_now_mv * contract.current_now_ma / 1_000_000
        if port.cable_info and port.cable_info.max_power_w and watts > port.cable_info.max_power_w:
            return ChargingDiagnostic(
                Bottleneck.CABLE_LIMIT, "Negotiated power exceeds the decoded cable rating.", True
            )
        return ChargingDiagnostic(Bottleneck.FINE, f"Negotiated power is {watts:g} W.", False)
    if partner_sources:
        return ChargingDiagnostic(
            Bottleneck.UNKNOWN,
            "Partner profiles are advertised; active contract is not exposed.",
            True,
        )
    return ChargingDiagnostic(
        Bottleneck.NO_CHARGER, "No negotiated power or partner offer is exposed by sysfs.", True
    )
