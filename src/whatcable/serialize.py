"""Stable JSON serialization for normalized reports."""

import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from typing import Any

from .models import Report
from .summary import summarize_advanced, summarize_port, summarize_usb


def to_dict(report: Report, *, include_raw: bool = False) -> dict[str, object]:
    def convert(value: Any) -> Any:
        if is_dataclass(value):
            return {
                field.name: convert(getattr(value, field.name))
                for field in fields(value)
                if include_raw or field.name != "raw"
            }
        if isinstance(value, Mapping):
            return {str(key): convert(item) for key, item in value.items()}
        if isinstance(value, tuple):
            return [convert(item) for item in value]
        return value

    document = convert(report)
    for data, port in zip(document["typec_ports"], report.typec_ports, strict=True):
        data["summary"] = convert(summarize_port(port))
    for data, device in zip(document["usb_devices"], report.usb_devices, strict=True):
        data["summary"] = convert(summarize_usb(device))
    for data, device in zip(document["advanced"], report.advanced, strict=True):
        data["summary"] = convert(summarize_advanced(device))
    return document


def dumps(report: Report, *, include_raw: bool = False) -> str:
    return json.dumps(to_dict(report, include_raw=include_raw), indent=2, sort_keys=True)
