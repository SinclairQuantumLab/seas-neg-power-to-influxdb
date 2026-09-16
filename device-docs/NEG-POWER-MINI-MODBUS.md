# NEG POWER MINI Modbus investigation

Date: 2026-09-15

Implementation follow-up: the initial read-only TCP relay is now implemented.
See [current validation](../.agents/VALIDATION.md). The investigation statements
below describe the earlier evidence-gathering stage; hardware validation remains
outstanding.

## Conclusion and evidence status

The supplied NEG POWER MINI Manager contains enough information to reconstruct
its principal monitoring register map. This is a map recovered from the vendor's
software, **not an official protocol specification or a live-device validation**.
No controller was contacted; no heating, configuration, or alarm-reset command
was sent. No relay or device client has been implemented.

Repository scope is reconsidered in [NEG POWER family research](NEG-POWER-FAMILY-RESEARCH.md).
The recommended scope is the NEG POWER product family, with separate MINI and
multicontroller register definitions. The earlier MINI-only repository naming
recommendation is superseded. `saes_neg_power_mini_client.py` remains a suitable
name for a MINI-specific implementation. The manufacturer's spelling is SAES;
`seas` preserves the user's existing repository naming choice.
This recovered map applies only to the examined MINI software. It does not
establish support for larger NEG POWER, LP, hybrid, SMALL, or NIOPS models.

## Primary evidence

Source installer supplied with the instrument:

`C:\Users\Joon\Box\IMAQ Lab\Manuals\Saes Nextorr Z200\Saes NEG POWER MINI USB Manual stick\saes-negmini_manager_setup.exe`

| File | Size | SHA-256 |
| --- | ---: | --- |
| Installer | 35025194 bytes | `9e3d58fe1b16b3c22a139927ba2fae5187d24790454f29da6e4398540a912995` |
| `NegMiniBackEnd.dll` | 92672 bytes | `d8d87c5f3ab06d88aa2bcfc3098a129873e8445de7b15bed067d340698071fff` |
| `NegMiniManager.exe` | 366080 bytes | `1a6b87368580d27e0d98e5912226bffba3f1031b4509df152868f960d296296d` |

The installer uses Qt Installer Framework. Embedded 7z streams were extracted
without running the installer. The application payload starts at byte offset
19872935 and is 15152069 bytes long. It contains the executable, backend DLL, and
Qt/runtime libraries, but no separate PDF, header, or protocol document.
Archive timestamps on the two vendor application files are 2019-05-28; this is
older than the supplied 2022 Rev.4 hardware manual. Backend version functions
return 0.0.1. These dates/version values do not establish the connected device's
firmware version.

The DLL exports descriptive C++ function names. Request construction,
reply decoding, getters, and GUI units were inspected independently. Addresses
below called RVA are offsets relative to each executable's image base.

## Transport and read requests

`NegMiniManager::sendMBRequests` (DLL RVA `0x2610`) constructs Qt data units with
register type **4 = HoldingRegisters** and calls `sendReadRequest`.
Consequently the read function is **0x03**, not 0x04. Register type 4 is a Qt enum,
not a Modbus function code. See [Qt's enum definition](https://doc.qt.io/archives/qt-5.15/qmodbusdataunit.html#RegisterType-enum).

The addresses below are the actual protocol addresses, without a 40001 display
offset. Do not subtract one from them when passing them to a zero-based Modbus
client API. Each register is a 16-bit word. For the 32-bit fields listed below,
the lower-address register is the low word: `low | (high << 16)`.

| Purpose | Starting address | Count | Request construction RVA |
| --- | --- | ---: | --- |
| Manufacturing/version data | `0x1000` (4096) | 3 | `0x2930` |
| Main status | `0x2000` (8192) | 14 | `0x2980` |
| General settings | `0x3000` (12288) | 4 | `0x29c6` |
| Work time extension | `0x200e` (8206) | 2 | `0x2a09` |
| Maximum pump temperature setting | `0x3004` (12292) | 1 | `0x2a4c` |

The final two reads are issued only when the software-version value read from
`0x1000..0x1001` is **greater than `0x00000200`**. Preserve this compatibility
condition until the firmware-version encoding and current firmware are verified.
Do not blindly extend the 14-register status read to 16 registers on every device.

For a status-only read, the Modbus PDU is `03 20 00 00 0e`. A TCP client adds its
MBAP header and the configured unit ID. The Manager passes its configured Modbus
ID into the shared request routine for TCP as well as RTU; the actual controller's
accepted TCP unit IDs have not been tested. Use the unit's configured port and ID.

## Recovered monitoring map

Follow-up (2026-09-16 UTC): the live read-only and additional vendor-code findings
in [validation notes](../.agents/VALIDATION.md) supersede the unresolved version,
time-unit and selected state/alarm descriptions in the original table below.
Detailed evidence is recorded at the end of this document.

`processMBReply` is at DLL RVA `0x1fc0`. It checks both the starting address and
the expected response length. The main 14-register decoder is at `0x24a9`.

| Register(s) | Decoded meaning | Conversion / limits of evidence |
| --- | --- | --- |
| `0x2000` | Controller status code | Unsigned 16-bit; preserve raw value. Full named-state mapping not yet audited. |
| `0x2001` | USB logging status | Unsigned 16-bit; getter maps values outside 1..6 to 0. Named meanings not yet audited. |
| `0x2002..0x2003` | Uptime | Unsigned 32-bit, low word first; time unit still requires confirmation. |
| `0x2004` | Controller temperature | Unsigned 16-bit kelvin; Celsius = raw - 273.15. |
| `0x2005` | Pump temperature | Unsigned 16-bit kelvin; Celsius = raw - 273.15, conditional on valid temperature sensing. |
| `0x2006` | Output voltage | Unsigned 16-bit; nominal scale 0.01 V per count. Manager returns `floor(raw / 10 + 0.5) / 10` V. |
| `0x2007` | Output current | Unsigned 16-bit; nominal scale 0.01 A per count. Manager returns `floor(raw / 10 + 0.5) / 10` A. |
| `0x2008..0x2009` | Active/on time | Unsigned 32-bit, low word first; time unit still requires confirmation. |
| `0x200a..0x200b` | Alarm latches | Unsigned 32-bit, low word first; individual bit meanings not yet audited. |
| `0x200c..0x200d` | Temperature error flags | Unsigned 32-bit, low word first. `isTempErr()` tests nonzero; per-error bit meanings not yet audited. |
| `0x200e..0x200f` | Work time, version-gated extension | Unsigned 32-bit, low word first. Manager divides by 3600 and displays whole hours. |

Voltage/current getter RVAs are `0x9180` and `0x9200`. The raw value is first
divided by 10, rounded to an integer, then divided by 10 again. Thus `1234`
produces 12.3 V and `456` produces 4.6 A in the Manager. Recording raw/100 would
retain more digits than the Manager; that choice should await a live comparison
and must not be mistaken for a verified measurement accuracy specification.

Temperature getters at `0x9280` and `0x9290` return the raw unsigned integer.
The GUI conversion routine at EXE RVA `0xe610` implements kelvin unchanged,
kelvin minus 273.15 for Celsius, and the corresponding Fahrenheit formula.
Do not treat an absent/broken thermocouple reading as a valid pump temperature.

The backend also exports `getVin()`, but the inspected main decoder sets its
backing field to zero. Its existence does **not** establish an input-voltage
register or a usable input-voltage measurement.

## Settings and identity

| Register(s) | Meaning | Observed interpretation |
| --- | --- | --- |
| `0x1000..0x1001` | Software version | Low-word-first 32-bit value; exact display encoding not yet audited. |
| `0x1002` | Hardware revision | Displayed as high byte, dot, low byte. |
| `0x3000` | Voltage setpoint | Raw / 100 V, decoded at `0x22cf..0x22e4`. |
| `0x3001` | Voltage ramp interval | Unsigned 16-bit; vendor log header labels it minutes. |
| `0x3002..0x3003` | Hold interval | Low-word-first unsigned 32-bit; vendor log header labels it minutes. Infinite/off sentinel semantics remain unverified. |
| `0x3004` | Pump temperature limit | Unsigned 16-bit kelvin; version-gated. Disabled sentinel remains unverified. |

## Observed control addresses (not validated or used)

The command branches also reveal writes to `0x4000` for start (1) and stop (0),
and to `0x4001` with value 1 for clearing alarm latches. Settings writes target
`0x3000` and, conditionally, `0x3004`. This is evidence of software behavior only;
it does not establish all sequencing, interlock, persistence, or firmware rules.
The request routine calls Qt `sendWriteRequest`; do not assume one fixed write
function code for both single-register and multi-register operations.

Initial implementation scope remains read-only monitoring. No write command
was sent during this investigation.

## Validation performed

The original DLL's status-decoding instructions and getter instructions were
emulated with Unicorn using synthetic 14-register data. This did not load or run
the Windows application, invoke OS APIs, or access any device/network.

- Checked register-to-field placement, including distinguishable high/low words.
- Checked 300 K controller and 600 K pump temperature recovery.
- Checked the vendor's voltage/current output for 1234 and 456 raw counts.
- Passed 24 additional getter checks around rounding boundaries and endpoints.

See `research/verification.json` and `research/verify_vendor_decode.py`.
The latter requires the exact source DLL above, plus `pefile` and `unicorn`.
Firmware compatibility, temperature validity, timing units, and live measurements
remain to be verified against the actual controller.

## Comparison with multi-channel NEG POWER

An operator's [2021 EPICS report](https://epics.anl.gov/tech-talk/2021/msg00866.php)
quotes a multi-output NEG POWER software manual with output blocks starting at
`0x1000 + 0x100 * output_index`, and VOUT offset `0x49`. That report also records
an illegal-address response, so it is a lead, not a validated alternate map.
Its quoted layout differs from the MINI Manager's status block at `0x2000`
and VOUT at `0x2006`. There is no basis for reusing one register map across them.

The supplied hardware manual `saes-neg_power_mini-user_manual-rev_4.pdf`,
pages 5, 12-13 and 20, independently establishes Ethernet Modbus TCP and RS232
Modbus RTU. Page 22 identifies MINI as part number `3B0110`.

## Next evidence needed

1. Confirm the physical unit is NEG POWER MINI and record firmware/hardware
   versions, TCP port, and configured Modbus ID from its settings.
2. Compare read-only responses for the exact vendor blocks with its front panel
   or Manager. Capture raw words and identify absent-temperature behavior.
3. Complete the status/alarm/temperature-error bit audit, confirm time units and
   special settings values, and seek the manufacturer protocol specification.

## Local project path

Canonical project directory:
`C:\Users\Joon\Projects\seas-neg-power-to-influxdb`

On 2026-09-15, the MINI-named project directory was renamed to the family-wide
name above at the user's request. All eight existing files were verified by
SHA-256 after the move. The previous MINI directory is a junction to this
canonical directory; the active thread's original `seas-neg-to-influxdb`
directory retains its `device-docs` junction, which still resolves to the same
data. These paths preserve existing links without duplicating the documents.
The Codex project's stored root has not been changed; select the canonical
directory when opening the project again. No local Git repository or GitHub
repository existed for this project at the time of the rename.

## Live interpretation follow-up: 2026-09-16 UTC

Read-only FC03 polling succeeded at the user-supplied `192.168.50.35:502`, unit
ID 1. The main relay ran with `--once --dry-run`, followed by three source polls.
No writes, alarm resets, heating commands or InfluxDB uploads were issued.
See `.agents/live-readonly-samples.json` for the samples and `.agents/VALIDATION.md`
for the failed hostname attempt and exact conditions. The following evidence
uses the same vendor binaries whose hashes are recorded above.

- **Firmware:** EXE `0x85c9..0x8771` extracts the low byte, middle byte and high
  16 bits, then joins them as high16.middle8.low8. Thus the observed register
  pair combined as 65536 (`0x00010000`) displays `1.0.0`.
- **Status:** DLL `0x6930` retains codes 1..5 (others become 0). EXE `0xe490`
  dispatches through the jump table at `0x312f8`: 0/1 unknown, 2 standby,
  3 ramp, 4 steady, 5 alarm, 6 offline. Code 6 is synthesized by the Manager
  when communication is absent (`getStatus`, DLL `0x9100`); it must not be
  described as a verified device register code. The live register was 2.
- **Time:** `getOntime` and `getUptime` feed EXE `0xe1a0` at call sites `0x8d04`
  and `0x8d53`. Its format string at `0x312b0` is `%ud-%02uh:%02um:%02us`, with
  divisions by 86400, 3600 and 60. Emulating the original formatter up to its
  QString call at `0xe232` verified inputs 59, 60, 3600, 86400 and 90061 seconds;
  results are in `.agents/vendor-time-format-check.json`. Live uptime increased
  by 11 over about 10.4 seconds, consistent with whole-second quantization.
  Active time remained zero; its reset/persistence behavior was not exercised.
- **Alarm bits:** DLL `isAlarm(Alarms)` at `0x9b40` tests `(flags >> index) & 1`.
  EXE `0x8e31..0x8f44` passes indices to widgets, whose labels are assigned at
  `0x1cb12..0x1cd23`: bit 0 overcurrent, 1 overvoltage, 2 undervoltage, 3 pump
  open, 6 interlock, 7 pump overtemperature, 8 VMonitor. Other bit meanings
  remain unknown. Only the no-latched-alarm value 0 was observed live.
- **Temperature fault:** live flags were 16 (bit 4), pump register 273 K, with
  the pump cable reportedly disconnected. Missing/open thermocouple is an
  inference, not an identified vendor enumeration or a controlled fault test.
  Both temperature fields continue to be recorded without rejection.
- **USB:** live code 2 with no USB memory stick, as confirmed by the user.
  Likely no storage / logging inactive, but not distinguishable without a
  comparison with media inserted. USB logging is independent of Modbus TCP.

README keeps these interpretations in its existing Meaning column. Raw field
names and runtime behavior are unchanged; estimates are marked `(Inferred)`.
