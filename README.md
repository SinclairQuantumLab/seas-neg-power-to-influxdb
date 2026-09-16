# seas-neg-power-to-influxdb

Poll one **SAES NEG POWER MINI** through Ethernet Modbus TCP and relay its
readings to InfluxDB. Only Read Holding Registers (FC03) requests are sent;
the app cannot start/stop heating, change settings, or reset alarms.

The project covers the NEG POWER product family. This initial implementation
supports **MINI over TCP only**. Multicontroller, LP, hybrid, SMALL, NIOPS and
RS232/RS485 are not implemented. There is no automatic model identification.
The MINI map comes from the supplied vendor Manager. Read-only polling has been
checked on one controller in standby; heating behavior and nonzero output
readings still need validation. Begin with the dry-run below.

## Requirements

- `uv` installed. The project specifies the Python version and dependencies;
  `uv sync` prepares the environment.

## Device configuration

- Confirm the controller is **NEG POWER MINI**.
- Enable Ethernet Modbus TCP and connect the controller to the network.
- Note its hostname/IP, TCP port (normally 502), and Modbus unit ID for
  `settings.toml`.

## Installation

1. Clone the repository and enter its directory:

    ```sh
    cd "$HOME/Projects"
    git clone --recursive https://github.com/SinclairQuantumLab/seas-neg-power-to-influxdb.git
    cd seas-neg-power-to-influxdb
    ```

    `--recursive` also clones the private `imaq-secret` submodule containing
    the upload credentials; access to that repository is required.

2. Install dependencies:

    ```bash
    uv sync
    ```

3. Copy and edit the settings template:

    ```powershell
    Copy-Item settings.toml.template settings.toml
    ```

    On Linux, use `cp settings.toml.template settings.toml`.

    | Setting | Meaning |
    | --- | --- |
    | `interval_s` | Seconds between polling-cycle starts; template uses 1 |
    | `host` | MINI hostname/IP; replace `<HOST>` |
    | `port` | Optional TCP port; defaults to 502 |
    | `unit_id` | Required controller Modbus ID; example `1` is not a verified default |
    | `timeout_s` | TCP connection or complete individual request timeout; template uses 3 |

    Unit ID is sent in TCP requests too. Each poll makes two requests on older
    firmware and three when the raw software-version value exceeds `0x200`.
    The timeout applies to each request, not the whole cycle.
    `settings.toml` is ignored by Git.

4. Test the device connection:

    ```bash
    uv run python main.py --settings settings.toml --once --dry-run
    ```

    This prints one reading without uploading and does not require InfluxDB
    credentials. Compare the readings with the controller display or Manager.

## Usage

1. Upload one poll:

    ```bash
    uv run python main.py --settings settings.toml --once
    ```

    Check the resulting point's tags, units and timestamp in InfluxDB before
    continuous collection.

2. Run continuously:

    ```bash
    uv run python main.py --settings settings.toml
    ```

For continuous service, adapt `supervisor/windows.conf.template` or
`supervisor/linux.conf.template` for the deployment's paths and account, then
register the program with Supervisor.

The first cycle starts immediately. Later cycles use cycle-start deadlines;
missed deadlines do not cause a catch-up burst. A source failure replaces the
connection immediately and retries the complete poll once. An unresolved cycle
or upload failure counts toward a lifetime limit of three; successes do not
reset the count. The third failure exits nonzero.
With `--once`, an unresolved failure exits nonzero immediately.

The Supervisor templates use `startsecs=30`, `startretries=5` and
`autorestart=unexpected`. A runtime error triggers a restart. If the controller
stays unreachable, subsequent runs exit within the 30-second startup window;
after five startup retries, Supervisor stops trying and enters FATAL. The relay
already collects data during STARTING; the 30 seconds are not a polling delay.
`timeout_s` applies to each connection attempt or individual Modbus request,
not to the whole process. For repeated TCP connection timeouts, allow this
conservative time budget: three failed cycles, two attempts per cycle, and up
to two polling-interval waits. The first attempt starts immediately.

```text
failure_budget_s = 3 × 2 × timeout_s + 2 × interval_s
startsecs > failure_budget_s + startup/cleanup margin

Current settings: 3 × 2 × 3 + 2 × 1 = 20 s; startsecs = 30 s
```

Recalculate if the timeout or polling interval changes. This budget covers
connection timeouts; DNS delays or multiple slow Modbus requests can take longer.
This limits repeated startup failures, not the total number of failures
separated by runs lasting at least 30 seconds. Start the
relay manually after restoring the controller. Apply these settings to an
already-installed Supervisor entry; repository templates do not update it.

Stop with `Ctrl+C`. Normal shutdown releases source and InfluxDB resources.
Supervisor owns stdout/stderr logs; there is no separate measurement log.
Each successful upload prints uptime (s), status, pump temperature (°C), heater
current (A), then output voltage (V); dry-run prints the complete record.
`Startup.ps1` and `Startup.sh` use the prepared `.venv` directly, without running
dependency installation during restarts.

## Data written to InfluxDB

One complete poll produces one point in fixed measurement **`seas-neg-power`**,
separate from the existing SIP measurement `seas-sip-power`.

| Tag | Value |
| --- | --- |
| `source` | `SAES NEG POWER MINI` |
| `host` | Configured hostname/IP |
| `port` | Configured TCP port as text |
| `ModbusID` | Configured unit ID as text |
| `Channel` | `1` |

The recovered map supplies no serial number. Endpoint tags identify the
configured connection, not the physical controller. Changing host/port/unit ID
creates a different series; replacing a controller at the same endpoint is not
detected automatically.

| Field | Type | Meaning |
| --- | --- | --- |
| `SoftwareVersionRaw` | integer | Packed firmware version: `major = raw >> 16`, `minor = (raw >> 8) & 255`, `patch = raw & 255`; observed `65536` = `1.0.0` |
| `HardwareRevision` | string | Major.minor hardware revision |
| `StatusRaw` | integer | Controller state: `2` = standby, `3` = ramp, `4` = steady, `5` = alarm, from the vendor Manager; other codes unresolved |
| `Status` | string, optional | `Standby`, `Ramp`, `Steady`, or `Alarm` for codes 2–5; omitted for unknown codes, while `StatusRaw` and all other readings are still uploaded; stdout shows `Unknown` |
| `USBLoggingStatusRaw` | integer | (Inferred) USB memory-stick logging state, independent of LAN communication; observed `2` with no stick connected, likely no storage / logging inactive; other codes unresolved |
| `UptimeRaw` | integer | Controller uptime in seconds; live counter progression and the Manager's time formatter support this unit |
| `InternalTemperature[°C]` | float | Controller temperature; `round(raw - 273.15, 2)` converts kelvin to °C |
| `PumpTemperature[°C]` | float | Pump temperature; `round(raw - 273.15, 2)` converts kelvin to °C; values are not filtered |
| `PumpTemperatureRaw` | integer | Original pump-temperature register in kelvin; sensor validity unverified |
| `OutputVoltageRaw` | integer | Original voltage register; nominally 0.01 V per count |
| `OutputCurrentRaw` | integer | Original heater-current register; nominally 0.01 A per count |
| `OutputVoltage[V]` | float | Voltage; `raw / 100` rounded half-up to 0.1 V, as recovered from the vendor Manager |
| `OutputCurrent[A]` | float | Heater current; `raw / 100` rounded half-up to 0.1 A, as recovered from the vendor Manager |
| `ActiveTimeRaw` | integer | Heating on-time in seconds, from the Manager's time formatter; observed `0` in standby; reset behavior unresolved |
| `AlarmFlagsRaw` | integer | Latched alarm bitmask (`0` = none); known bit indices: 0 overcurrent, 1 overvoltage, 2 undervoltage, 3 pump open, 6 interlock, 7 pump overtemperature, 8 VMonitor; other bits unresolved |
| `TemperatureErrorFlagsRaw` | integer | (Inferred) Sensor-error bitmask; observed `16` (bit 4) with the reported disconnected pump cable, likely missing/open thermocouple; exact fault meanings unresolved |
| `TotalWorkingTime[s]` | integer, optional | Work time; `low + 65536 * high` in seconds, with no scaling; firmware value > `0x200` only |

Temperatures are uploaded in Celsius, rounded to two decimal places to avoid
floating-point conversion artifacts; this does not add sensor resolution.
`PumpTemperatureRaw` preserves the original register alongside its Celsius
conversion. The user observed 273 with the pump cable disconnected; this becomes
-0.15 °C, not proof of a valid sensor reading. Disconnected/faulty-sensor handling
remains unverified, so the relay does not filter 273 or infer sensor validity.
Individual alarm booleans are not exposed yet.
Heater current is not an ion current; the relay computes no pressure.

New samples use `InternalTemperature[°C]` instead of `InternalTemperature[K]`.
Existing InfluxDB history is unchanged; update queries using the former kelvin
field when switching to this version.

The timestamp is the host's aware UTC time after the final successful response.
The poll spans multiple requests and is not an atomic hardware snapshot. If any
required block fails, no partial point is uploaded. Electrical raw counts are
retained alongside rounded values; extra digits are not an accuracy claim.

## Troubleshooting

- **Connection refused / timeout:** check endpoint, TCP port, Modbus TCP mode,
  network path and unit ID. `interval_s` does not change request timeouts.
- **Modbus exception `0x02`:** the device rejected the address/range. Verify
  MINI model and firmware. Do not substitute a multicontroller map. A required
  extension failure rejects the poll.
- **Header/payload error:** the connection is discarded. Compare a read-only
  exchange with the vendor Manager for that firmware.
- **Missing work time:** expected when the raw software version is <= `0x200`.
- **Raw fields:** some now have identified units or codes, listed above; field
  names remain unchanged. `(Inferred)` marks an estimate, and `(Unresolved)`
  marks a meaning that could not be established.
- **Missing `auth.toml`:** for an existing clone made without `--recursive`, run
  `git submodule update --init --recursive` with authorized access, or use
  `--dry-run`. Never put credentials in settings or source code.
- **Missing `.venv` interpreter:** run `uv sync` in this directory.

## Validation status

Validation includes synthetic frames, vendor-code emulation, a local TCP server,
and successful read-only polling of the user's controller on 2026-09-16 UTC
(2026-09-15 local). It reported firmware `1.0.0`, standby, zero heater output,
and pump temperature `273 K`. Repeated reads supported uptime in seconds.
This check did not upload to InfluxDB or start heating. Nonzero output readings,
temperature-error meanings and other operating states remain unverified live.

## Developer's note

`main.py` follows the direct SIP relay structure. The self-contained
`saes_neg_power_mini_client.py` owns fixed-address FC03 reads and parsing and has
no InfluxDB dependency. There is no generic driver framework or placeholder
multicontroller implementation. Tests and continuation notes live in `.agents/`.

```bash
uv run pytest -q
uv run ruff check .
```

- [Implementation provenance and 13-repository survey](.agents/PROVENANCE.md)
- [Validation and remaining work](.agents/VALIDATION.md)
- [Product-family research](device-docs/NEG-POWER-FAMILY-RESEARCH.md)
- [Recovered MINI map](device-docs/NEG-POWER-MINI-MODBUS.md)

Historical emulation scripts under `device-docs/research` are preserved artifacts
outside production lint and do not run as part of the relay.
