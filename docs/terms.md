# Terms and device identification

## Identifying a connected device

WhatCable reads information the Linux USB and Type-C subsystems expose. A connected
hard disk, mouse, keyboard, dock, or other USB peripheral can appear in **USB
devices**. Its device-provided `product` and `manufacturer` strings often identify
the model and maker. `VID:PID` is a hexadecimal vendor/product identifier pair;
it is useful for looking up a model or distinguishing similar devices. The USB
`serial` field can distinguish two units of the same model if the device exposes
one. The USB topology key identifies where it is plugged in for the current scan;
it is not a permanent device identity.

USB *class* describes a broad function, such as Mass Storage for many disks or HID
(Human Interface Device) for many mice and keyboards. A composite device can have
several interfaces with different classes. Some devices report class `00` at the
device level and put their useful class codes only on interfaces; others use a
vendor-specific class. Therefore a generic or missing class does not mean the
device is unknown to Linux. WhatCable uses interface classes and standard HID boot
protocol codes where available to label likely keyboards and mice; this is not a
full decode of every HID function. `whatcable --json` contains the normalized
interface class, subclass, protocol, and driver fields when the scanner finds
them. WhatCable does not query disk
capacity, SMART data, mounted filesystems, and other device-specific subsystems.

Manufacturer/product strings and serial numbers come from the device and can be
absent or generic. On live hardware, the optional `lsusb` command and system
`usb.ids` file can supply more descriptive names. A small built-in VID table is a
further fallback, so a missing vendor label does not imply that no vendor ID exists. For
the most complete identification data exposed by this program, use
`whatcable --json --raw` or turn on **Show details** in the GUI.

## USB, cable, and power vocabulary

| Term | Meaning |
| --- | --- |
| **USB-C / Type-C port** | A physical connector represented by the kernel's Type-C class, often named `port0`, `port1`, etc. |
| **Partner** | The device connected to a Type-C port; it can be a charger, dock, display, or other device. |
| **Power role** | Whether the port supplies power (`source`) or receives it (`sink`), if exposed. This differs from the USB data role. |
| **USB PD** | USB Power Delivery, the protocol used to advertise and negotiate power profiles over USB-C. |
| **PDO** | Power Data Object: an advertised voltage/current or power profile. It is not proof that this profile is currently selected. |
| **PPS / AVS** | Programmable Power Supply / Adjustable Voltage Supply: PD profile types that allow a voltage range rather than one fixed voltage. |
| **UCSI** | USB Type-C Connector System Software Interface. Some Linux drivers expose the current power contract through a UCSI power-supply device. |
| **Negotiated power** | Current contract voltage times current from the power-supply interface. It is not a direct wattmeter measurement of a peripheral's consumption. |
| **E-marker** | Electronic identification in some USB-C cables. It may advertise cable type, current rating, speed, and vendor. An absent e-marker record does not establish a cable's real limits. |
| **Alternate mode / SVID** | A nonstandard use of USB-C lanes such as DisplayPort; the SVID identifies the mode's vendor or standard. Matching IDs offer limited compatibility evidence, not proof of an active display link. |
| **Hub / root hub** | A USB device that fans one connection out into several. A root hub represents the host controller itself. |
| **VID:PID** | Hexadecimal USB vendor ID and product ID. Useful for identifying a product family, though not always a unique physical unit. |
| **Mb/s / Gb/s** | Megabits or gigabits per second. USB link speed and cable rating differ from real application throughput. |

WhatCable preserves uncertainty where kernel data is missing. A missing partner
offer, cable identity, or active contract must not be read as evidence that the
hardware lacks the corresponding capability.
