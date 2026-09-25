# Sysfs test fixtures

Fixture roots mirror the paths below `sys/` so they can be passed directly to
`SysfsRoots.from_root()` and the CLI's `--sysfs-root` option.  They are synthetic
and deliberately contain only stable kernel-ABI attributes needed by a test; tests
that model a particular PD, UCSI, Thunderbolt, or unplug scenario build their small
tree in a temporary directory beside the assertion.

`no-typec/` represents a machine whose kernel exposes ordinary USB devices but no
Type-C class.  It validates the normal, non-error absence of Type-C support.  Live
hardware results are not checked in because they include host-specific topology,
serial numbers, and driver state.
