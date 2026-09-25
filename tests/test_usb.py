import importlib.util
import json
from dataclasses import replace
from pathlib import Path

import pytest

from whatcable.altmode import AltModeCompatibility, cable_altmode_compatibility
from whatcable.chrome_ec import enumerate_chrome_ec
from whatcable.cli import _text, main
from whatcable.device_info import _parse_lsusb, device_type, display_name, vendor_label
from whatcable.diagnostic import Bottleneck, assess_charging
from whatcable.gui.app import _pdo_limit, _pdo_range
from whatcable.gui.settings import Settings
from whatcable.gui.settings import load as load_settings
from whatcable.gui.settings import save as save_settings
from whatcable.manager import scan
from whatcable.models import PowerDataObject
from whatcable.pd import parse_capability_directory
from whatcable.pd_decoder import decode_cable_vdo, decode_identity
from whatcable.serialize import to_dict
from whatcable.summary import summarize_port
from whatcable.sysfs import SysfsRoots
from whatcable.usb_classes import interface_lookup
from whatcable.vendors import lookup as vendor_name


def write(root: Path, relative: str, value: str) -> None:
    path = root / "sys/bus/usb/devices" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


def test_enumerates_usb_topology(tmp_path: Path) -> None:
    for name, value in {
        "usb1/busnum": "1\n",
        "usb1/devnum": "1\n",
        "usb1/bDeviceClass": "09\n",
        "1-2/busnum": "1\n",
        "1-2/devnum": "2\n",
        "1-2/idVendor": "1234\n",
        "1-2/idProduct": "abcd\n",
        "1-2/product": "Test Cable Device\n",
        "1-2/speed": "480\n",
        "1-2/tx_lanes": "2\n",
        "1-2/rx_lanes": "2\n",
        "1-2/bDeviceClass": "0e\n",
    }.items():
        write(tmp_path, name, value)
    report = scan(SysfsRoots.from_root(tmp_path))
    assert [device.key for device in report.usb_devices] == ["1-2", "usb1"]
    child, root = report.usb_devices
    assert child.parent_key == "usb1"
    assert root.child_keys == ("1-2",)
    assert child.vendor_id == 0x1234
    assert (child.tx_lanes, child.rx_lanes) == (2, 2)
    assert child.class_code == 0x0E
    document = to_dict(report)
    assert document["schema_version"] == 1
    assert "raw" not in document["usb_devices"][0]
    assert document["usb_devices"][0]["summary"]["category"] == "usb"


def test_reusable_no_typec_fixture() -> None:
    fixture = Path(__file__).parent / "fixtures" / "no-typec"
    report = scan(SysfsRoots.from_root(fixture))
    assert not report.typec_ports
    assert [device.key for device in report.usb_devices] == ["1-1", "usb1"]


def test_lsusb_labels_match_the_same_bus_device_and_ids(monkeypatch) -> None:
    fixture = Path(__file__).parent / "fixtures" / "no-typec"
    device = scan(SysfsRoots.from_root(fixture)).usb_devices[0]
    device = replace(
        device,
        sysfs_path="/sys/bus/usb/devices/1-1",
        bus_number=1,
        device_number=4,
        vendor_id=0x258A,
        product_id=0x01A0,
        product="Gaming KB",
    )
    records = _parse_lsusb("Bus 001 Device 004: ID 258a:01a0 SINO WEALTH Gaming KB\n")
    monkeypatch.setattr("whatcable.device_info._database", lambda: ({}, {}))
    monkeypatch.setattr("whatcable.device_info._lsusb_records", lambda _bucket: records)
    assert vendor_label(device) == "SINO WEALTH"
    assert display_name(device) == "Gaming KB"
    assert vendor_label(replace(device, device_number=5)) != "SINO WEALTH"
    assert vendor_label(replace(device, sysfs_path=str(fixture / "device"))) != "SINO WEALTH"


def test_default_cli_shows_internal_devices_but_counts_hidden_root_hubs(tmp_path: Path) -> None:
    write(tmp_path, "usb1/idVendor", "1d6b\n")
    write(tmp_path, "usb1/idProduct", "0002\n")
    write(tmp_path, "1-1/idVendor", "1234\n")
    write(tmp_path, "1-1/idProduct", "5678\n")
    write(tmp_path, "1-1/product", "Built-in Camera\n")
    write(tmp_path, "1-1/removable", "fixed\n")
    report = scan(SysfsRoots.from_root(tmp_path))
    output = _text(report, include_all=False)
    assert "Built-in Camera" in output
    assert "1 USB devices shown; 1 root hubs hidden; use --all" in output
    assert "[1d6b:0002]" not in output
    assert "[1d6b:0002]" in _text(report, include_all=True)


def test_usb_interface_protocol_identifies_mouse_and_keyboard(tmp_path: Path) -> None:
    write(tmp_path, "1-2/bDeviceClass", "00\n")
    write(tmp_path, "1-2/1-2:1.0/bInterfaceClass", "03\n")
    write(tmp_path, "1-2/1-2:1.0/bInterfaceSubClass", "01\n")
    write(tmp_path, "1-2/1-2:1.0/bInterfaceProtocol", "01\n")
    write(tmp_path, "1-2/1-2:1.1/bInterfaceClass", "03\n")
    write(tmp_path, "1-2/1-2:1.1/bInterfaceSubClass", "01\n")
    write(tmp_path, "1-2/1-2:1.1/bInterfaceProtocol", "02\n")
    device = scan(SysfsRoots.from_root(tmp_path)).usb_devices[0]
    assert device_type(device) == "Keyboard, Mouse"


def test_typec_identity_is_read_by_attribute_name(tmp_path: Path) -> None:
    base = tmp_path / "sys/class/typec/port0/port0-partner"
    identity = base / "identity"
    identity.mkdir(parents=True)
    (base / "supports_usb_power_delivery").write_text("1\n")
    (identity / "id_header").write_text("ff008001\n")
    (identity / "cert_stat").write_text("12345678\n")
    (identity / "product_type_vdo1").write_text("00000444\n")
    mode = base / "port0-partner.0"
    mode.mkdir()
    (mode / "svid").write_text("ff01\n")
    (mode / "mode").write_text("1\n")
    cable = tmp_path / "sys/class/typec/port0-cable"
    cable.mkdir()
    (cable / "type").write_text("active\n")
    cable_identity = cable / "identity"
    cable_identity.mkdir()
    (cable_identity / "id_header").write_text("0000046d\n")
    (cable_identity / "product_type_vdo1").write_text("00000444\n")
    plug = tmp_path / "sys/class/typec/port0-plug0/port0-plug0.0"
    plug.mkdir(parents=True)
    (plug / "svid").write_text("ff01\n")
    report = scan(SysfsRoots.from_root(tmp_path))
    port = report.typec_ports[0]
    assert port.partner is not None
    assert port.partner.supports_usb_power_delivery is True
    assert port.partner.identity is not None
    assert port.partner.identity.id_header == 0xFF008001
    assert port.partner.alt_modes[0].svid == 0xFF01
    assert port.cable is not None and port.cable.cable_type == "active"
    assert port.cable_info is not None and port.cable_info.vendor_name == "Logitech"
    assert cable_altmode_compatibility(port) is AltModeCompatibility.YES
    cable_vdo = decode_cable_vdo(port.partner.identity, "active")
    assert cable_vdo is not None and (cable_vdo.speed_gbps, cable_vdo.max_voltage_v) == (80, 40)
    decoded = decode_identity(port.partner.identity)
    assert decoded.vendor_id == 0x8001
    text = _text(report, include_all=True)
    assert "Cable alternate-mode compatibility: yes" in text


def test_parses_fixed_and_pps_pdo_directories(tmp_path: Path) -> None:
    root = tmp_path / "source-capabilities"
    fixed, pps = root / "1:fixed_supply", root / "2:programmable_supply"
    fixed.mkdir(parents=True)
    pps.mkdir()
    (fixed / "voltage").write_text("5000\n")
    (fixed / "maximum_current").write_text("3000\n")
    (pps / "minimum_voltage").write_text("3300\n")
    (pps / "maximum_voltage").write_text("11000\n")
    (pps / "maximum_current").write_text("3000\n")
    (pps / "pps_power_limited").write_text("1\n")
    caps = parse_capability_directory(root, role="source", provenance="partner")
    assert caps is not None
    assert [(pdo.supply_type, pdo.maximum_power_mw) for pdo in caps.pdos] == [
        ("fixed_supply", 15000),
        ("programmable_supply", 33000),
    ]
    assert caps.pdos[1].flags["pps_power_limited"] == "1"


def test_parses_variable_and_battery_pdo_directories(tmp_path: Path) -> None:
    root = tmp_path / "source-capabilities"
    variable, battery = root / "1:variable_supply", root / "2:battery"
    variable.mkdir(parents=True)
    battery.mkdir()
    (variable / "minimum_voltage").write_text("5000\n")
    (variable / "maximum_voltage").write_text("12000\n")
    (variable / "maximum_current").write_text("2000\n")
    (battery / "minimum_voltage").write_text("9000\n")
    (battery / "maximum_voltage").write_text("20000\n")
    (battery / "maximum_power").write_text("45000\n")
    caps = parse_capability_directory(root, role="source", provenance="partner")
    assert caps is not None
    assert [
        (pdo.supply_type, pdo.min_voltage_mv, pdo.max_voltage_mv, pdo.maximum_power_mw)
        for pdo in caps.pdos
    ] == [("variable_supply", 5000, 12000, 24000), ("battery", 9000, 20000, 45000)]


def test_parses_spr_adjustable_voltage_ranges(tmp_path: Path) -> None:
    avs = tmp_path / "source-capabilities/5:spr_adjustable_voltage_supply"
    avs.mkdir(parents=True)
    (avs / "maximum_current_9V_to_15V").write_text("3000\n")
    (avs / "maximum_current_15V_to_20V").write_text("2000\n")
    (avs / "maximum_current_20V_to_28V").write_text("1800\n")
    caps = parse_capability_directory(avs.parent, role="source", provenance="partner")
    assert caps is not None
    assert [
        (pdo.min_voltage_mv, pdo.max_voltage_mv, pdo.maximum_power_mw) for pdo in caps.pdos
    ] == [(9000, 15000, 45000), (15000, 20000, 40000), (20000, 28000, 50400)]


def test_parses_legacy_raw_fixed_pdo(tmp_path: Path) -> None:
    raw = tmp_path / "source-capabilities"
    raw.write_text("0001912c\n")  # 5 V, 3 A
    caps = parse_capability_directory(raw, role="source", provenance="partner")
    assert caps is not None and caps.pdos[0].maximum_power_mw == 15000


def test_pd_provenance_keeps_port_self_separate_from_partner(tmp_path: Path) -> None:
    port = tmp_path / "sys/class/typec/port0"
    own = port / "usb_power_delivery/source-capabilities/1:fixed_supply"
    peer = port / "port0-partner/usb_power_delivery/source-capabilities/1:fixed_supply"
    own.mkdir(parents=True)
    peer.mkdir(parents=True)
    (own / "voltage").write_text("5000\n")
    (own / "maximum_current").write_text("3000\n")
    (peer / "voltage").write_text("20000\n")
    (peer / "maximum_current").write_text("3250\n")
    report = scan(SysfsRoots.from_root(tmp_path))
    capabilities = report.typec_ports[0].pd_capabilities
    assert [(item.provenance, item.pdos[0].maximum_power_mw) for item in capabilities] == [
        ("port-self", 15000),
        ("partner", 65000),
    ]


def test_ucsi_partner_pdn_capabilities_are_a_partner_offer(tmp_path: Path) -> None:
    port = tmp_path / "sys/class/typec/port0"
    capability = port / "port0-partner/pd0/source-capabilities/1:fixed_supply"
    capability.mkdir(parents=True)
    (capability / "voltage").write_text("20000\n")
    (capability / "maximum_current").write_text("3250\n")
    report = scan(SysfsRoots.from_root(tmp_path))
    caps = report.typec_ports[0].pd_capabilities
    assert [(item.provenance, item.pdos[0].maximum_power_mw) for item in caps] == [
        ("partner", 65000)
    ]


def test_explicit_connector_name_correlates_usb_device_to_typec_port(tmp_path: Path) -> None:
    (tmp_path / "sys/class/typec/port0/usb1-port4").mkdir(parents=True)
    device = tmp_path / "sys/bus/usb/devices/1-4"
    device.mkdir(parents=True)
    report = scan(SysfsRoots.from_root(tmp_path))
    assert report.typec_ports[0].usb_device_keys == ("1-4",)


def test_pd_class_fallback_uses_device_ancestry(tmp_path: Path) -> None:
    port = tmp_path / "sys/class/typec/port0"
    port.mkdir(parents=True)
    target = tmp_path / "devices/port0-partner"
    target.mkdir(parents=True)
    pd = tmp_path / "sys/class/usb_power_delivery/pd0"
    (pd / "source-capabilities/1:fixed_supply").mkdir(parents=True)
    (pd / "source-capabilities/1:fixed_supply/voltage").write_text("9000\n")
    (pd / "source-capabilities/1:fixed_supply/maximum_current").write_text("3000\n")
    (pd / "version").write_text("1.0\n")
    (pd / "device").symlink_to(target)
    report = scan(SysfsRoots.from_root(tmp_path))
    caps = report.typec_ports[0].pd_capabilities
    assert [(item.provenance, item.version, item.pdos[0].maximum_power_mw) for item in caps] == [
        ("partner-class", "1.0", 27000)
    ]
    assert "Partner offer: fixed_supply: 9 V @ 3 A" in _text(report, include_all=True)
    assert assess_charging(report.typec_ports[0]).status is Bottleneck.UNKNOWN


def test_pd_direct_link_and_class_fallback_are_deduplicated(tmp_path: Path) -> None:
    port = tmp_path / "sys/class/typec/port0"
    port.mkdir(parents=True)
    pd = tmp_path / "sys/class/usb_power_delivery/pd0"
    capability = pd / "source-capabilities/1:fixed_supply"
    capability.mkdir(parents=True)
    (capability / "voltage").write_text("5000\n")
    (capability / "maximum_current").write_text("3000\n")
    (port / "usb_power_delivery").symlink_to(pd)
    (pd / "device").symlink_to(port)
    report = scan(SysfsRoots.from_root(tmp_path))
    assert len(report.typec_ports[0].pd_capabilities) == 1


def test_ucsi_contract_is_normalized_and_separate_from_pdos(tmp_path: Path) -> None:
    (tmp_path / "sys/class/typec/port0").mkdir(parents=True)
    psy = tmp_path / "sys/class/power_supply/ucsi-source-psy-USBC000:001"
    psy.mkdir(parents=True)
    for name, value in {"online": "1", "voltage_now": "20000000", "current_now": "3000000"}.items():
        (psy / name).write_text(f"{value}\n")
    report = scan(SysfsRoots.from_root(tmp_path))
    contract = report.typec_ports[0].power_supply_contract
    assert contract is not None
    assert (contract.online, contract.voltage_now_mv, contract.current_now_ma) == (
        True,
        20000,
        3000,
    )
    assert "Negotiated power: 60 W" in _text(report, include_all=False)
    assert assess_charging(report.typec_ports[0]).inferred is False
    assert summarize_port(report.typec_ports[0]).status == "charging"


def test_ambiguous_ucsi_fallback_becomes_a_scan_warning(tmp_path: Path) -> None:
    (tmp_path / "sys/class/typec/port0").mkdir(parents=True)
    for controller in ("USBC000", "USBC001"):
        (tmp_path / f"sys/class/power_supply/ucsi-source-psy-{controller}:001").mkdir(parents=True)
    report = scan(SysfsRoots.from_root(tmp_path))
    assert report.typec_ports[0].power_supply_contract is None
    assert "2 UCSI power supplies" in report.warnings[0]
    assert "Warnings" in _text(report, include_all=True)


def test_cli_json_uses_fixture_root(tmp_path: Path, capsys) -> None:
    device = tmp_path / "sys/bus/usb/devices/1-1"
    device.mkdir(parents=True)
    (device / "idVendor").write_text("1234\n")
    (device / "idProduct").write_text("5678\n")
    main(["--json", "--sysfs-root", str(tmp_path)])
    document = json.loads(capsys.readouterr().out)
    assert document["schema_version"] == 1
    assert document["usb_devices"][0]["vendor_id"] == 0x1234


def test_cli_numbered_details_accept_mixed_separators_and_include_raw(
    tmp_path: Path, capsys
) -> None:
    (tmp_path / "sys/class/typec/port0/port0-partner").mkdir(parents=True)
    write(tmp_path, "usb1/idVendor", "1d6b\n")
    write(tmp_path, "usb1/idProduct", "0002\n")
    write(tmp_path, "1-1/idVendor", "1234\n")
    write(tmp_path, "1-1/idProduct", "5678\n")
    write(tmp_path, "1-1/product", "Test disk\n")
    write(tmp_path, "1-1/uevent", "line one\nline two\n")
    advanced = tmp_path / "sys/bus/thunderbolt/devices/0-1"
    advanced.mkdir(parents=True)
    (advanced / "device_name").write_text("Test dock\n")
    args = ["--sysfs-root", str(tmp_path)]

    main(args)
    listing = capsys.readouterr().out
    assert "- [1] port0: connected" in listing
    assert "- [2] Test disk [1234:5678]" in listing
    assert "- [3] Test dock:" in listing
    assert "[1d6b:0002]" not in listing

    main(["-i", "3,2", "2", *args])
    detail = capsys.readouterr().out
    assert detail.index("[3] Advanced source") < detail.index("[2] USB device")
    assert detail.count("[2] USB device") == 1
    assert "idVendor: 1234" in detail
    assert 'uevent: "line one\\nline two"' in detail
    assert "Vendor id: 4660" in detail

    main(["--json", "--info", "2,", "3", *args])
    selected = json.loads(capsys.readouterr().out)
    assert [(item["number"], item["kind"]) for item in selected["items"]] == [
        (2, "usb"),
        (3, "advanced"),
    ]
    assert selected["items"][0]["details"]["raw"]["idVendor"] == "1234"

    main(["--all", "-i", "3", *args])
    assert "USB device" in capsys.readouterr().out


def test_cli_info_rejects_unknown_numbers_and_watch(tmp_path: Path, capsys) -> None:
    (tmp_path / "sys/bus/usb/devices/1-1").mkdir(parents=True)
    args = ["--sysfs-root", str(tmp_path)]
    with pytest.raises(SystemExit) as error:
        main(["-i", "2", *args])
    assert error.value.code == 2
    assert "not in this report" in capsys.readouterr().err
    with pytest.raises(SystemExit) as error:
        main(["-i", "1,x", *args])
    assert error.value.code == 2
    assert "invalid item number" in capsys.readouterr().err
    with pytest.raises(SystemExit) as error:
        main(["--watch", "-i", "1", *args])
    assert error.value.code == 2
    assert "cannot be combined" in capsys.readouterr().err


def test_watch_json_emission_is_one_line(tmp_path: Path, capsys, monkeypatch) -> None:
    device = tmp_path / "sys/bus/usb/devices/1-1"
    device.mkdir(parents=True)
    monkeypatch.setattr("whatcable.cli.events", lambda: iter(()))
    main(["--json", "--watch", "--sysfs-root", str(tmp_path)])
    assert len(capsys.readouterr().out.splitlines()) == 1


def test_connect_waits_for_new_cable_and_shows_only_its_port(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    typec = tmp_path / "sys/class/typec"
    (typec / "port0/port0-partner").mkdir(parents=True)
    (typec / "port1").mkdir()
    calls = 0

    def attach(_seconds: float) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            identity = typec / "port1-cable/identity"
            identity.mkdir(parents=True)
            (identity.parent / "type").write_text("passive\n")
            (identity / "id_header").write_text("0000046d\n")
            (identity / "product_type_vdo1").write_text("00000442\n")
            (identity / "custom_attribute").write_text("example\n")
            (typec / "port1/port1-partner").mkdir()

    monkeypatch.setattr("whatcable.cli.time.sleep", attach)
    main(["-C", "--sysfs-root", str(tmp_path)])
    captured = capsys.readouterr()
    assert "Waiting for a USB-C cable connection" in captured.err
    assert "port1" in captured.out
    assert "port0" not in captured.out
    assert "Cable info:" in captured.out
    assert "Vendor name: Logitech" in captured.out
    assert "custom_attribute: example" in captured.out
    assert calls == 2


def test_connect_reports_missing_cable_identity_as_json(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    typec = tmp_path / "sys/class/typec"
    (typec / "port0").mkdir(parents=True)
    calls = 0

    def attach(_seconds: float) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            (typec / "port0/port0-partner").mkdir()

    monkeypatch.setattr("whatcable.cli.time.sleep", attach)
    main(["--connect", "--json", "--sysfs-root", str(tmp_path)])
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["items"][0]["kind"] == "typec"
    assert result["items"][0]["details"]["key"] == "port0"
    assert result["items"][0]["details"]["cable_info"] is None
    assert "Cable identity is not exposed" in captured.err


def test_connect_rejects_watch_and_info(tmp_path: Path, capsys) -> None:
    for option in ("--watch", "--info"):
        arguments = ["--connect", option, "1"] if option == "--info" else ["-C", option]
        with pytest.raises(SystemExit) as error:
            main([*arguments, "--sysfs-root", str(tmp_path)])
        assert error.value.code == 2
        assert "cannot be combined" in capsys.readouterr().err


def test_raw_json_includes_raw_sysfs_attributes(tmp_path: Path, capsys) -> None:
    device = tmp_path / "sys/bus/usb/devices/1-1"
    device.mkdir(parents=True)
    (device / "idVendor").write_text("1234\n")
    main(["--json", "--raw", "--sysfs-root", str(tmp_path)])
    document = json.loads(capsys.readouterr().out)
    assert document["usb_devices"][0]["raw"]["idVendor"] == "1234"
    assert "Raw: idVendor=1234" in _text(
        scan(SysfsRoots.from_root(tmp_path), include_raw=True), include_all=True, include_raw=True
    )


def test_diagnostic_is_explicit_when_sysfs_has_no_charger_data(tmp_path: Path) -> None:
    (tmp_path / "sys/class/typec/port0").mkdir(parents=True)
    report = scan(SysfsRoots.from_root(tmp_path))
    diagnostic = assess_charging(report.typec_ports[0])
    assert diagnostic.status is Bottleneck.NO_CHARGER
    assert diagnostic.inferred is True


def test_cli_hides_empty_ports_unless_all_is_requested(tmp_path: Path) -> None:
    (tmp_path / "sys/class/typec/port0").mkdir(parents=True)
    report = scan(SysfsRoots.from_root(tmp_path))
    assert "port0:" not in _text(report, include_all=False)
    assert "no visible USB-C ports" in _text(report, include_all=False)
    assert "port0: empty" in _text(report, include_all=True)


def test_cli_empty_sysfs_explains_missing_kernel_data(tmp_path: Path) -> None:
    assert "no USB-C ports exposed by sysfs" in _text(
        scan(SysfsRoots.from_root(tmp_path)), include_all=False
    )
    assert "no USB devices exposed by sysfs" in _text(
        scan(SysfsRoots.from_root(tmp_path)), include_all=False
    )


def test_missing_attributes_during_scan_are_nonfatal(tmp_path: Path) -> None:
    # Represents a device removed while sysfs enumeration is in progress.
    (tmp_path / "sys/bus/usb/devices/1-2").mkdir(parents=True)
    (tmp_path / "sys/class/typec/port0").mkdir(parents=True)
    report = scan(SysfsRoots.from_root(tmp_path))
    assert [device.key for device in report.usb_devices] == ["1-2"]
    assert report.typec_ports[0].partner is None


def test_vendor_lookup() -> None:
    assert vendor_name(0x046D) == "Logitech"
    assert interface_lookup(0x08, 0x08) == "UAS"


def test_thunderbolt_source_is_optional_and_fixture_driven(tmp_path: Path) -> None:
    device = tmp_path / "sys/bus/thunderbolt/devices/0-1"
    device.mkdir(parents=True)
    (device / "vendor_name").write_text("Example\n")
    (device / "device_name").write_text("Dock\n")
    report = scan(SysfsRoots.from_root(tmp_path))
    assert [(item.source, item.name) for item in report.advanced] == [("thunderbolt", "Dock")]
    assert to_dict(report)["advanced"][0]["summary"]["category"] == "advanced"


def test_usb4_source_is_optional_and_fixture_driven(tmp_path: Path) -> None:
    device = tmp_path / "sys/bus/usb4/devices/0-1"
    device.mkdir(parents=True)
    (device / "device_name").write_text("USB4 Dock\n")
    (device / "generation").write_text("3\n")
    report = scan(SysfsRoots.from_root(tmp_path))
    assert [(item.source, item.name, item.summary) for item in report.advanced] == [
        ("usb4", "USB4 Dock", "Gen 3")
    ]


def test_usb_debugfs_source_is_optional_and_fixture_driven(tmp_path: Path) -> None:
    debug = tmp_path / "sys/kernel/debug/usb/devices"
    debug.parent.mkdir(parents=True)
    debug.write_text("T: Bus=01 Lev=01\nS: Manufacturer=Acme\nS: Product=Debug Device\n")
    report = scan(SysfsRoots.from_root(tmp_path), include_raw=True)
    assert [(item.source, item.name) for item in report.advanced] == [
        ("usb_debugfs", "Debug Device")
    ]
    assert "Raw: manufacturer=Acme" in _text(report, include_all=True, include_raw=True)


def test_chrome_ec_absence_is_an_empty_optional_source(tmp_path: Path) -> None:
    assert enumerate_chrome_ec(tmp_path / "no-cros-ec") == ()


def test_gui_settings_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    settings = Settings(show_hubs=True, show_details=True)
    save_settings(settings, path)
    assert load_settings(path) == settings


def test_gui_reports_missing_native_dependency() -> None:
    if importlib.util.find_spec("gi") is not None:
        pytest.skip("native GTK smoke testing is performed on GTK-capable systems")
    from whatcable.gui.app import main as gui_main

    with pytest.raises(SystemExit, match="PyGObject"):
        gui_main()


def test_gui_pdo_labels_describe_advertised_profiles_without_selection() -> None:
    pdo = PowerDataObject(
        position=1,
        supply_type="programmable_supply",
        min_voltage_mv=3300,
        max_voltage_mv=11000,
        maximum_current_ma=3000,
        maximum_power_mw=33000,
        peak_current=None,
        sysfs_path="/fixture/pdo",
    )
    assert _pdo_range(pdo) == "3.3–11 V"
    assert _pdo_limit(pdo) == "up to 3 A"
