# seas-neg-power-to-influxdb

Poll one **SAES NEG POWER MINI** through Ethernet Modbus TCP and relay its
readings to InfluxDB. Only Read Holding Registers (FC03) requests are sent;
the app cannot start/stop heating, change settings, or reset alarms.

The project covers the NEG POWER product family. This initial implementation
supports **MINI over TCP only**. Multicontroller, LP, hybrid, SMALL, NIOPS and
RS232/RS485 are not implemented. There is no automatic model identification.
The MINI map comes from the supplied vendor Manager and has not yet been
checked against a physical controller. Begin with the dry-run below.

## Requirements

- An actual NEG POWER MINI with Ethernet Modbus TCP enabled and reachable.
  Confirm the controller model, not just the attached pump model.
- Its hostname/IP, configured TCP port (normally 502), and Modbus unit ID.
- Git, `uv`, and Python 3.11 or newer.
- Lab InfluxDB credentials in `imaq-secret/auth.toml` for uploads. Dry-run works
  without credentials and does not construct an InfluxDB client.

## Installation

1. Open the local project. This initial repository has not been published to
   GitHub, so there is no remote clone URL yet.

    ```powershell
    cd "$env:USERPROFILE\Projects\seas-neg-power-to-influxdb"
    ```

    The private `imaq-secret` repository is registered as a credential submodule.
    On an upload-enabled deployment, initialize it with authorized GitHub access:

    ```bash
    git submodule update --init --recursive
    ```

    This obtains credentials at the location expected by the app. It is not
    required for dry-run. Once a remote relay repository exists, clone it with
    `--recurse-submodules` to obtain the credential submodule together.

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
    | `interval_s` | Seconds between polling-cycle starts; template uses 30 |
    | `host` | MINI hostname/IP; replace `<HOST>` |
    | `port` | Optional TCP port; defaults to 502 |
    | `unit_id` | Required controller Modbus ID; example `1` is not a verified default |
    | `timeout_s` | TCP connection or complete individual request timeout; template uses 3 |

    Unit ID is sent in TCP requests too. Each poll makes two requests on older
    firmware and three when the raw software-version value exceeds `0x200`.
    The timeout applies to each request, not the whole cycle.
    `settings.toml` is ignored by Git.

4. For continuous service, adapt `supervisor/windows.conf.template` or
   `supervisor/linux.conf.template` for the deployment's paths and account.
   Supervisor installation and service registration are separate deployment steps.

## Usage

1. Query once and print the record without loading credentials or uploading:

    ```bash
    uv run python main.py --settings settings.toml --once --dry-run
    ```

    Compare output voltage/current and controller temperature with the front
    panel or vendor Manager. A response alone does not prove model/firmware
    compatibility or sensor validity.

2. After validating readings and preparing credentials, upload one poll:

    ```bash
    uv run python main.py --settings settings.toml --once
    ```

    Check the resulting point's tags, units and timestamp in InfluxDB before
    continuous collection.

3. Run continuously:

    ```bash
    uv run python main.py --settings settings.toml
    ```

The first cycle starts immediately. Later cycles use cycle-start deadlines;
missed deadlines do not cause a catch-up burst. A source failure replaces the
connection immediately and retries the complete poll once. An unresolved cycle
or upload failure counts toward a lifetime limit of three; successes do not
reset the count. The third failure exits nonzero for Supervisor to restart.
With `--once`, an unresolved failure exits nonzero immediately.

Stop with `Ctrl+C`. Normal shutdown releases source and InfluxDB resources.
Supervisor owns stdout/stderr logs; there is no separate measurement log.
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
| `SoftwareVersionRaw` | integer | Firmware value; display encoding unresolved |
| `HardwareRevision` | string | Major.minor hardware revision |
| `StatusRaw` | integer | Uninterpreted controller status |
| `USBLoggingStatusRaw` | integer | Uninterpreted USB logging register |
| `UptimeRaw` | integer | Uptime register pair; time unit unverified |
| `InternalTemperature[K]` | integer | Controller temperature in kelvin |
| `PumpTemperatureRaw` | integer | Sensor register, not a validated temperature |
| `OutputVoltageRaw` | integer | Original voltage register |
| `OutputCurrentRaw` | integer | Original heater-current register |
| `OutputVoltage[V]` | float | Voltage using Manager's 0.1 V rounding |
| `OutputCurrent[A]` | float | Heater current using Manager's 0.1 A rounding |
| `ActiveTimeRaw` | integer | Active-time register pair; time unit unverified |
| `AlarmFlagsRaw` | integer | Uninterpreted 32-bit alarm flags |
| `TemperatureErrorFlagsRaw` | integer | Uninterpreted 32-bit sensor error flags |
| `TotalWorkingTime[s]` | integer, optional | Work-time extension; firmware value > `0x200` only |

`PumpTemperatureRaw` may contain an absent/faulty-sensor value. Do not convert it
into a temperature dashboard until sensor validity and sentinels are verified.
No normalized pump-temperature or individual alarm boolean is exposed yet.
Heater current is not an ion current; the relay computes no pressure.

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
- **Raw values have no units/names:** this is a limit of the recovered map,
  not a missing conversion setting.
- **Missing `auth.toml`:** initialize the credential submodule with authorized
  access or use `--dry-run`. Never put credentials in settings or source code.
- **Missing `.venv` interpreter:** run `uv sync` in this directory.

## Validation status

Validation uses synthetic register frames, the previously recovered vendor-code
behavior, and a local TCP server. No real NEG controller query, InfluxDB upload,
or Supervisor service registration has been performed. Model/firmware
compatibility, sensor validity and unresolved raw semantics still need verification.

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
