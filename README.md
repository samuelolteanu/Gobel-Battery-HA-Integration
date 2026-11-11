---
description: Fork of the Gobel Power Battery Home Assistant integration with in-place reconfiguration, resilient serial reconnect and removable stale devices
---

# Gobel Battery Monitor: multi-BMS fork

[Deutsch](docs/de/README.md) | [简体中文](docs/zh-cn/README.md) (upstream translations, not updated for this fork)

A fork of [fancyui/Gobel-Battery-HA-Integration](https://github.com/fancyui/Gobel-Battery-HA-Integration), a native Home Assistant integration for LiFePO4 battery banks running Pace BMS, JK BMS or TDT BMS hardware. No MQTT broker is needed: devices and sensors are created directly in Home Assistant, and several battery banks (different serial ports or IPs) can run side by side as separate config entries.

This fork targets setups with **several BMSes on USB serial adapters**, especially in a virtual machine, where device paths can change after a host reboot, a rescue, or a change of USB passthrough order.

---

## What this fork changes

All changes are relative to upstream version 2.0.12. Entity and device unique IDs are untouched, so existing entities, renames, dashboards and automations keep working.

### 1. Reconfigure an existing entry (no delete and re-add)

Upstream can only set the connection once, at creation. If the serial port changed, the only option was to create a new entry, which produces new entities and loses renamed ones and automation references.

This fork adds a **Reconfigure** action (entry menu ⋮ → *Reconfigure*):

- **Serial entries:** port, baud rate and poll interval.
- **Network entries (Ethernet/WiFi):** IP address, TCP port and poll interval.
- **Port picker:** a dropdown lists what exists on the system, in this order: `/dev/serial/by-id/*`, `/dev/serial/by-path/*`, `/dev/ttyUSB*`, `/dev/ttyACM*`. The current value is always included, and you can still type a custom path.
- **Validation:** a serial path that does not exist is rejected with an error.
- **In place:** the entry is updated and reloaded; entities keep their IDs because unique IDs are derived from the entry ID, not from the port.

The entry's own `unique_id` (the original port path) is not changed by reconfiguring. This does not affect entities. It only means you cannot later add a *new* entry on that same original path.

### 2. Rate-limited serial reconnect

Upstream retried opening the serial port inside every failed read or write. When a port disappeared (USB re-enumeration, passthrough swap), this produced thousands of failed `open()` calls and a flood of error lines. In this fork:

- Reconnect attempts happen **at most once every 10 seconds** (`BMSCommunication.try_reconnect()`).
- While the port is missing, the coordinator raises a quiet `UpdateFailed` ("port not available, retrying") instead of polling.
- When the path comes back, the connection recovers on its own, with no reload needed.
- The "No active connection to disconnect" message is now debug level.

### 3. Stale pack devices can be deleted

If a pack device ever appeared on the wrong entry (for example, two entries had their ports swapped and one polled the other's batteries), it stayed as an undeletable ghost, because the integration never allowed device removal.

The integration now implements `async_remove_config_entry_device`:

- A **pack** device can be deleted only if the BMS is **not currently reporting** that pack.
- The **Total** device can never be deleted.
- Deleting a device removes its entities.

### 4. UI labels

Added `custom_components/gobel_battery/translations/en.json`, so the config, serial, network and reconfigure steps show proper field labels and error text instead of raw keys.

### Files touched

| File | Change |
|---|---|
| `config_flow.py` | `async_step_reconfigure`, serial port listing, port validation |
| `bms_comm.py` | `try_reconnect()` with a 10 s limit, `is_connected`, quieter disconnect logging |
| `coordinator.py` | Quiet `UpdateFailed` while the port is unavailable |
| `__init__.py` | `async_remove_config_entry_device` |
| `translations/en.json` | New: UI strings |

---

## Cell balancing sensors

Per-cell binary sensors named **Pack NN Cell NN Balancing** (`mdi:scale-balance`) are created for every cell the BMS reports, and are on while that cell is being balanced (passive or active). They are decoded from the full balancing bitmasks, so several cells balancing at once are all shown.

| BMS / interface | Per-cell balancing sensors |
|---|---|
| Pace RS232 | Yes (passive and active; protocol V1 reports passive only) |
| TDT RS232 | Yes |
| Pace RS485, Pace WiFi | No in this version: the raw passive/active status bytes are parsed, but no per-cell sensors are created |
| JK RS485 | No per-cell sensors; a pack **balance current** sensor is provided instead |

---

## Key features (inherited from upstream)

- **Multi-BMS compatibility:** Pace BMS (RS232, RS485, WiFi), JK BMS (55AA passive protocol), TDT BMS (RS232).
- **Connectivity:** RS232-USB, RS232-to-Ethernet, RS232-to-WiFi, RS485-to-Ethernet, RS485-to-WiFi.
- **Native entities:** sensors and binary sensors for cell voltages, temperatures, capacity, current, SOC, faults and per-cell balancing (see above).
- **Grouping:** overall metrics (Total SOC, Voltage, Current, ...) under an aggregate device, with a child device per parallel-connected battery pack.
- **GUI setup:** everything is configured through *Settings → Devices & Services*.

---

## BMS connection notes

**Pace BMS**
- RS232-WiFi/Ethernet module or RS232-USB cable required.
- Connect to the **RS232** or **WiFi** interface of the **master** BMS.
- Set the master's DIP switch (dial) to **1000**.

**JK BMS**
- RS485-WiFi/Ethernet module or RS485-USB cable required.
- Connect to the **RS485B** or **RS485C** interface of the **master** BMS.
- Set the master's DIP switch (dial) to **0000**.

**Baud rate:** JK BMS and Gobel PC BMS typically use 115200. Other BMSes are usually 9600 or 115200. A wrong baud rate may not produce an immediate error but leads to timeouts or corrupted data.

---

## Installation

### Home Assistant Marketplace (Home Assistant 2026.11 or newer)
The Marketplace (*Settings → Marketplace*) replaced HACS in 2026.11 and uses the same catalog and `hacs.json`. This fork is a custom repository:

1. Go to **Settings → Marketplace**.
2. Select **Add from link** (upper right).
3. Enter `samuelolteanu/Gobel-Battery-HA-Integration` (or the full GitHub URL) and select **Add**. If the content type is not detected, choose **Integration** and add again.
4. Open the project and select **Install**. If a restart is requested, use the repair under *Settings → System → Repairs*.
5. Add the integration under *Settings → Devices & services*, or follow the setup flow that opens after installing.

Adding a custom repository needs a GitHub connection (pairing code, done in the Marketplace). New versions show up under *Settings → Updates*.

If the upstream integration or an earlier install of this fork is already present, the fork replaces it (same domain `gobel_battery`). Your existing entries and entities are kept. HA may ask for an extra confirmation when a component replaces an existing one.

### HACS (Home Assistant 2026.10 and older)
HACS cannot be installed on 2026.11 or newer, and updating moves its installs into the Marketplace automatically. On older versions: HACS → Integrations → ⋮ → **Custom repositories** → add `https://github.com/samuelolteanu/Gobel-Battery-HA-Integration` as **Integration**, download, restart.

### Manual
1. Copy `custom_components/gobel_battery` into `/config/custom_components/`.
2. Restart Home Assistant.

---

## Configuration

1. *Settings → Devices & Services → Add Integration → Gobel Battery Monitor*.
2. Choose the BMS type, connection type (serial / ethernet / wifi) and battery port (RS232 / RS485).
3. Enter the serial port and baud rate, or IP and TCP port.
4. For more battery banks, repeat *Add Integration*. Each bank is its own entry.

To change the connection later, use **⋮ → Reconfigure** on the entry. Do not delete and re-add it.

---

## Stable serial ports (VMs, Proxmox)

Which path to use depends on how the adapters present themselves:

- **`/dev/serial/by-id/...`** is stable and preferred **only if each adapter has a unique serial number**. Many cheap adapters do not. Two identical CH340 adapters (`1a86:7523`) have no serial, so they all map to the same by-id name, and by-id cannot tell them apart.
- **`/dev/serial/by-path/...`** identifies the adapter by the USB port it is plugged into. Inside a VM that is the *virtual* controller port (for example `pci-0000:07:1b.0-usb-0:1:1.0-port0`), which is assigned when the device is attached.
- **`/dev/ttyUSBn`** depends on enumeration order and is the least stable.

Recommendations for Proxmox:

- Pass adapters through **by host port** (`usbN: host=<bus>-<port>`) rather than by vendor:product ID, so identical adapters are not mixed up.
- Keep the attach order fixed (`usb0` before `usb1`), including when you hot-plug devices from a script. The guest port numbers follow the attach order.
- If you swap devices between VMs, restore them in the same order.

To inspect what is distinguishable inside the VM:

```
udevadm info -q property /dev/ttyUSB0 | grep -i 'ID_PATH\|ID_SERIAL'
```

---

## Troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| `could not open port ... No such file or directory` | Adapter re-enumerated or detached from the VM | Check passthrough; the integration retries every 10 s and recovers once the path is back |
| `No data received from BMS: device reports readiness to read but returned no data` | The port vanished mid-read, or another process uses it | Check the path exists; make sure nothing else opens the adapter |
| Entry stuck in "not ready, retrying" | Initial connection failed | Use **Reconfigure** to pick the correct path |
| Ghost pack device that cannot be deleted | Pack was created while the entry pointed at another BMS | Open the device → ⋮ → **Delete** (allowed when the pack is not currently reported) |
| Entities show unavailable for a few cycles after a glitch | Cached values are held for 3 consecutive failed reads, then dropped | Expected; they recover with the next successful read |

When reporting a disconnect, include the first `Errno 2` or `No data received` lines and the lines just before them.

---

## Dashboard example

<a href="https://www.gobelpower.com/ha_dashboard_integration_ap84.html">Online Home Assistant dashboard generator</a> (upstream project)

![image](img/screen-1.png)

---

## Credits and license

Original integration by [@fancyui](https://github.com/fancyui). This fork adds the changes listed above. See `LICENSE` for the license terms.
