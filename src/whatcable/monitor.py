"""pyudev monitor with a small debounce for CLI and future GLib integration."""

import time
from collections.abc import Iterator

import pyudev

SUBSYSTEMS = ("usb", "typec", "usb_power_delivery", "power_supply")


def create_monitor() -> pyudev.Monitor:
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    for subsystem in SUBSYSTEMS:
        monitor.filter_by(subsystem)
    monitor.start()
    return monitor


def events(debounce_seconds: float = 0.5) -> Iterator[None]:
    monitor = create_monitor()
    while True:
        if monitor.poll(timeout=None) is None:
            continue
        deadline = time.monotonic() + debounce_seconds
        while time.monotonic() < deadline:
            monitor.poll(timeout=max(0, deadline - time.monotonic()))
        yield None
