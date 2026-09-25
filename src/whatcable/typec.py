"""Type-C port, partner, and named identity enumeration."""

from pathlib import Path

from .cable import cable_info
from .models import EMPTY_RAW, AltMode, Identity, TypeCCable, TypeCPartner, TypeCPlug, TypeCPort
from .pd import class_capabilities_for_port, parse_capability_directory
from .sysfs import SysfsRoots, attributes, iter_dirs, read_bool, read_int, read_text


def _identity(path: Path, include_raw: bool) -> Identity | None:
    identity_path = path / "identity"
    if not identity_path.is_dir():
        return None
    values = [
        read_int(identity_path / name, 16)
        for name in (
            "id_header",
            "cert_stat",
            "product",
            "product_type_vdo1",
            "product_type_vdo2",
            "product_type_vdo3",
        )
    ]
    if not any(value is not None for value in values):
        return None
    return Identity(
        *values,
        sysfs_path=str(identity_path),
        raw=attributes(identity_path) if include_raw else EMPTY_RAW,
    )


def _partner(path: Path, include_raw: bool) -> TypeCPartner | None:
    partner_path = path / f"{path.name}-partner"
    if not partner_path.is_dir():
        return None
    return TypeCPartner(
        sysfs_path=str(partner_path),
        accessory_mode=read_text(partner_path / "accessory_mode"),
        supports_usb_power_delivery=read_bool(partner_path / "supports_usb_power_delivery"),
        pd_revision=read_text(partner_path / "usb_power_delivery_revision"),
        identity=_identity(partner_path, include_raw),
        alt_modes=_alt_modes(partner_path),
        raw=attributes(partner_path) if include_raw else EMPTY_RAW,
    )


def _alt_modes(path: Path) -> tuple[AltMode, ...]:
    modes = []
    for child in iter_dirs(path):
        if not child.name.startswith(f"{path.name}."):
            continue
        active = read_text(child / "active")
        modes.append(
            AltMode(
                str(child),
                read_int(child / "svid", 16),
                read_int(child / "mode"),
                read_int(child / "vdo", 16),
                (active == "1") if active is not None else None,
            )
        )
    return tuple(modes)


def _child_or_sibling(port: Path, suffix: str) -> Path | None:
    name = f"{port.name}-{suffix}"
    for candidate in (port / name, port.parent / name):
        if candidate.is_dir():
            return candidate
    return None


def _cable(port: Path, include_raw: bool) -> TypeCCable | None:
    path = _child_or_sibling(port, "cable")
    return (
        TypeCCable(str(path), read_text(path / "type"), _identity(path, include_raw))
        if path
        else None
    )


def _plug(port: Path, include_raw: bool) -> TypeCPlug | None:
    path = _child_or_sibling(port, "plug0")
    return TypeCPlug(str(path), _identity(path, include_raw), _alt_modes(path)) if path else None


def _capabilities(path: Path, provenance: str, revision: str | None, include_raw: bool):
    """Read direct PD links only; no name-based association is allowed here."""
    result = []
    pd_path = path / "usb_power_delivery"
    pd_nodes = [pd_path, *[child for child in iter_dirs(path) if child.name.startswith("pd")]]
    for node in pd_nodes:
        for directory, role in (("source-capabilities", "source"), ("sink-capabilities", "sink")):
            caps = parse_capability_directory(
                node / directory,
                role=role,
                provenance=provenance,
                revision=revision,
                version=read_text(node / "version"),
                include_raw=include_raw,
            )
            if caps is not None:
                result.append(caps)
    return tuple(result)


def _deduplicate_capabilities(capabilities):
    unique = []
    seen = set()
    for capability in capabilities:
        try:
            key = str(Path(capability.sysfs_path).resolve())
        except OSError:
            key = capability.sysfs_path
        if key not in seen:
            unique.append(capability)
            seen.add(key)
    return tuple(unique)


def enumerate_ports(roots: SysfsRoots, include_raw: bool = False) -> tuple[TypeCPort, ...]:
    ports: list[TypeCPort] = []
    for path in iter_dirs(roots.typec):
        if not path.name.startswith("port") or "-" in path.name:
            continue
        partner = _partner(path, include_raw)
        capabilities = list(
            _capabilities(
                path, "port-self", read_text(path / "usb_power_delivery_revision"), include_raw
            )
        )
        if partner is not None:
            capabilities.extend(
                _capabilities(
                    path / f"{path.name}-partner", "partner", partner.pd_revision, include_raw
                )
            )
        capabilities.extend(class_capabilities_for_port(roots, path.name, include_raw=include_raw))
        cable = _cable(path, include_raw)
        ports.append(
            TypeCPort(
                sysfs_path=str(path),
                key=path.name,
                data_role=read_text(path / "data_role"),
                power_role=read_text(path / "power_role"),
                power_operation_mode=read_text(path / "power_operation_mode"),
                usb_capability=read_text(path / "usb_capability"),
                typec_revision=read_text(path / "usb_typec_revision"),
                pd_revision=read_text(path / "usb_power_delivery_revision"),
                partner=partner,
                cable=cable,
                cable_info=cable_info(cable),
                plug=_plug(path, include_raw),
                pd_capabilities=_deduplicate_capabilities(capabilities),
                raw=attributes(path) if include_raw else EMPTY_RAW,
            )
        )
    return tuple(ports)
