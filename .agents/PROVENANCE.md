# Implementation provenance

Survey: 2026-09-15. Skill preflight: feature/to-influxdb-development,
status=current-dirty, ahead/behind 0/0; existing skill edits left untouched.

## Refreshed organization corpus

All 13 matching relays were accessible, nonempty and not archived. Inspected
default branch trees, main scripts, README/instructions, settings where present,
metadata, startup/deployment files and recent history. No submodules were cloned
and no credential files were read. Non-relay drivers, Supervisor servers,
Grafana administration and analysis/design repositories were excluded by purpose.

| Repository | Branch | Survey head | Relevant shape / boundary |
| --- | --- | --- | --- |
| seas-sip-power-to-influxdb | main | a8e35bd | Primary: direct single-device snapshot relay |
| siglent-spd3000-to-influxdb | main | 5c478e1 | Per-channel points, direct script, selected readings |
| arroyo-to-influxdb | main | 6b8dbd5 | Direct script, subsystem/channel points, whole-batch retry |
| hicube-neo-to-influxdb | main | 2574129 | OPC UA snapshots; optional local logs now present |
| dataq-to-influxdb | main | 8d9be79 | Streaming callbacks; reconnect settings now in TOML |
| iqair-to-influxdb | main | e6d85bc | Async BLE/classes; inappropriate architecture for this source |
| koheron_ctl-to-influxdb | main | e8e5143 | Multiple independent serial devices and busy skips |
| multivisor-to-influxdb | main | cd8d3d8 | HTTP session refresh; host tag precedent |
| LFI3751-to-influxdb | master | 6385a81 | Small client plus direct polling/recovery |
| ULE-Ion-pump-to-influxdb | main | 0719232 | Small client plus direct polling/recovery |
| nut-to-influxdb | main | 8794e30 | Host identity tag; operator documentation |
| sensorpush-to-influxdb | main | bc2df19 | Historical backfill, inappropriate acquisition model |
| pico-tc08-to-influxdb | main | 63c249f | SDK/local logging/optional upload; architecture counterexample |

The skill's August snapshot is stale in several places: SIP was renamed and its
measurement conflict resolved; DATAQ gained settings; HiCube gained local logs;
Siglent and Arroyo are additional relays. These changes were not automatically
imported as universal conventions.

## Adaptation decisions

The user's local SIP checkout was clean at main/f0ba1e4. Remote main/a8e35bd
differs in Startup.sh only. This task did not alter or pull the user's SIP tree.

- `main.py`, pyproject, .gitignore, .gitattributes, .python-version, logging helpers,
  launcher and Supervisor templates were adapted from local SIP/f0ba1e4.
- Preserved its literal trusted-settings/auth/InfluxDB blocks, synchronous write,
  three CLI options, immediate whole-poll reconnect/retry, lifetime threshold 3,
  cycle-start timing, signal handling and cleanup. No configurable measurement,
  extra reconnect delay, app classes, local data log, or multi-device scheduler.
- Kept the simple f0ba1e4 shell launcher, also present in Siglent/5c478e1 and
  HiCube/2574129. Remote SIP's a8e35bd interactive terminal/SN parsing additions
  are not needed by this Supervisor-managed source.
- User later rejected indefinite restart for the intermittently powered NEG
  controller. Both Supervisor templates retain startretries=5 and use
  autorestart=unexpected with startsecs=30. The settings template now matches
  the user's actual interval_s=1. Existing relay lifetime threshold
  and single reconnect/retry remain. Following a runtime failure, persistent
  controller unavailability causes restarted runs to fail during STARTING,
  exhausting startretries. This is not a lifetime restart cap. User explicitly
  preferred basic Supervisor configuration over an additional restart counter.
  Reference: https://docs.supervisord.org/configuration.html
- Source difference: MINI uses TCP FC03 and several register blocks, replacing
  SIP UDP/Read All entirely. Implemented only this small read subset with Python
  sockets, following SIP's self-contained source-client boundary. Partial TCP
  reads, full-request deadlines, transaction/unit/function/length checks and
  disconnect-on-error are covered independently.
- Kept snake_case source attributes and human-readable InfluxDB names in main.
  `seas-neg-power` is a new fixed measurement consistent with the accepted repo
  scope and Spinal-Case preference; it does not rename SIP's deployed series.
- Source identity is endpoint host/port/unit ID, explicitly not a serial number.
  Host tagging has NUT/multivisor precedent; the endpoint components distinguish
  TCP ports and Modbus units because the recovered MINI map lacks a serial.
  Channel="1" follows per-output tagging in Siglent/Arroyo and leaves a clear
  path for later multichannel records. This is new NEG schema, not a universal
  Sinclair tag contract. Endpoint changes create different series.
- State/alarm/timing/sensor values with incomplete semantics remain Raw integers.
  At the user's subsequent request, temperature registers are interpreted as
  kelvin and uploaded in Celsius. PumpTemperatureRaw remains alongside the
  conversion; no sensor-validity claim or sentinel filtering is added.
  Current is heater amperes, not SIP nanoamperes. Electrical display rounding is
  recovered from vendor code; raw register counts are retained alongside it.
- Follow-up: user requested a string Status field and second-position stdout
  status. SourceSample.status maps vendor-confirmed codes 2..5 to names and
  uses Unknown otherwise for stdout. Per user follow-up, unknown codes omit the
  uploaded Status field while preserving StatusRaw and all readings. Evidence: MINI map's
  live interpretation follow-up, DLL 0x6930/0x9100 and EXE 0xe490.
- Identity + status are mandatory. Work-time extension is read only for firmware
  >0x200. Any required-block failure rejects the entire poll. Configuration reads
  and all writes were deliberately omitted from this initial monitoring scope.
- `imaq-secret` gitlink matches SIP's 95b488d9a44389c3bf8077dd1a064993610c6a9b;
  .gitmodules was copied, without fetching or inspecting the private repository.
- Initialized local main Git repository only. No GitHub repository or remote
  publication was created by this implementation task.

## Protocol evidence

- device-docs/NEG-POWER-MINI-MODBUS.md and its synthetic vendor-code emulation.
- device-docs/NEG-POWER-FAMILY-RESEARCH.md for model boundaries.
- Modbus Organization specifications index:
  https://www.modbus.org/modbus-specifications (FC03 / TCP MBAP references).

No hardware endpoint was provided. Real MINI model/firmware/port/unit ID,
temperature validity and live values remain unverified.
