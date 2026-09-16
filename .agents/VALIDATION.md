# Validation and handoff

## README setup organization

Requirements now lists uv; device/network prerequisites have their own Device
configuration section. Python/dependency versions remain project-managed and
credentials are explained at submodule setup. Installation ends with the
one-shot dry-run connection test; service setup follows Usage. Documentation
only, checked for command preservation and `git diff --check`.

## Supervisor timeout documentation

README includes the conservative TCP-connection-failure budget
3 * 2 * timeout_s + 2 * interval_s and explains startsecs headroom, immediate
first polling, and the limits for DNS/multiple slow requests. Checked against
the retry/loop scheduling code and current settings. Documentation only;
`git diff --check` passed. No service change or new live test.

## Finite restart policy follow-up

User rejected indefinite restart for an intermittently powered controller.
Final policy: both Supervisor templates use startsecs=30, startretries=5 and
autorestart=unexpected. This supersedes the intermediate autorestart=false
proposal. Persistent connection timeouts exhaust relay retries in about 20 s
with 1 s polling; settings.toml.template now also uses 1 s, matching the actual
settings. Restarted runs thus fail within STARTING and exhaust Supervisor retries.
Runs lasting >=30 s reset
startup failure accounting, so this is not a lifetime restart cap. The relay
lifetime threshold 3 and one immediate reconnect/retry are unchanged. Existing
28 tests and Ruff passed before this config-only correction; final template
parsing and diff checks passed. No installed Supervisor entry was modified,
service restarted, or live supervisor state transition tested.

## String status follow-up

Added string field Status alongside unchanged integer StatusRaw: 2 Standby,
3 Ramp, 4 Steady, 5 Alarm. At the user's follow-up request, unknown codes omit
the Status field but keep StatusRaw and all other readings; stdout shows Unknown.
The source sample owns this
vendor-derived interpretation. In particular device code 6 is not treated as
the Manager's synthetic Offline state. Successful upload stdout now places
Status second, after uptime. README schema updated.

`uv run pytest -q`: 28 passed, including string line-protocol serialization,
stdout order and unknown-code preservation. Ruff and diff checks passed.
No live upload or running-service restart was performed for this change.

## Stdout summary follow-up

Successful upload summaries now show uptime in seconds, PumpTemperature[°C],
current, then voltage, at the user's request. Dry-run still prints the complete record.
InfluxDB fields are unchanged. Existing suite: 27 passed; Ruff and diff checks
passed. No live upload or running-service restart was performed for this change.

## Live read-only interpretation follow-up

2026-09-16 03:24-03:25 UTC (2026-09-15 local): configured `exp-neg-pump`
failed DNS resolution. User supplied `192.168.50.35`. A temporary settings copy
with this address, port 502 and unit ID 1 successfully ran the real
`main.py --once --dry-run`. Original settings were not changed. Three subsequent
FC03-only polls are recorded in `live-readonly-samples.json`; uptime increased
10979 -> 10985 -> 10990 over about 10.4 seconds. Stable values: firmware 65536,
hardware 1.0, state 2, USB state 2, internal temperature 296 K, pump 273 K,
V/I/on-time/work-time/alarm flags all zero, temperature-error flags 16.

Further vendor-code inspection established firmware byte formatting, states
2..5, seven alarm-bit labels, and seconds for both time counters. Original EXE
time formatter emulation passed five boundaries (`vendor-time-format-check.json`).
Temperature fault bit 4 is only inferred to indicate a missing/open sensor
from the user's disconnected-cable report. User also confirmed no USB stick is
connected; USB state 2 is inferred as no storage / logging inactive, independently
of LAN communication. Exact USB state names require comparison with media present.
README Meaning cells updated; no runtime/schema changes or sensor filtering.
No heating/configuration commands, InfluxDB writes, or service restart performed.
The historical initial-validation notes below predate this successful live check.

## Conversion documentation follow-up

README documents conversions concisely in the existing Meaning column, per
the user's preference. Cross-checked against the source decoder, main.py field
mapping and recovered-map investigation.
Documentation only; no runtime change or new live validation.

## Celsius upload follow-up

User requested kelvin-to-Celsius conversion and reported a pump register value
of 273 with the pump cable disconnected. Both temperature fields now upload
Celsius; the pump raw field and error flags remain available. This is unit
conversion only, without a sensor-validity decision. Existing schema/line-protocol
test verifies 300 K -> 26.85 °C and 273 K -> -0.15 °C, including a nonzero error
flag. `uv run pytest -q`: 27 passed; `uv run ruff check .` and `git diff --check`:
passed. No live device/InfluxDB access or service restart was performed.

Date: 2026-09-15. Initial implementation, local main branch, no remote published.

## Current offline evidence

- `uv sync`: passed, Python 3.11.14; uv.lock created.
- `uv run pytest -q`: 27 passed.
- `uv run ruff check .`: passed. Historical device-docs/research emulation code
  is explicitly excluded; runtime, logging helpers and new tests are checked.
- `uv run python main.py --help`: passed; --settings, --once, --dry-run available.
- Real socket loopback: synthetic server bound only to 127.0.0.1, verified exact
  FC03 identity/status/extension requests and decoded returned values.
- Other tests: fragmented reads, MBAP transaction/protocol/unit mismatch,
  malformed length/function/byte-count, exception response, EOF, timeout,
  complete-request deadline, reconnect, firmware extension boundary, word order,
  vendor rounding, required-block failure, exact InfluxDB schema/serialization,
  dry-run credential isolation, immediate retry, lifetime threshold, upload
  failure and cleanup.
- Credential submodule is registered at the selected SIP revision and remains
  uninitialized. Only public repository metadata was used; no credentials read.

The first lint run found pre-existing style issues in the historical vendor
emulation script. It was preserved, excluded as an investigation artifact, and
not rewritten as part of the relay. No existing application tests were present
before this task.

## Not validated live

No actual controller connection, InfluxDB upload/query, or Supervisor service
launch/restart. No real deployment settings were copied from SIP or guessed.
The loopback check is not hardware validation. Windows and Linux launcher files
were adapted from the selected SIP snapshot; Linux execution was not performed.

## Next steps

1. Confirm the instrument's actual controller model is MINI.
2. Supply host, configured TCP port and Modbus ID in ignored settings.toml.
3. Run `uv run python main.py --settings settings.toml --once --dry-run` and
   compare against the panel/Manager, recording exact firmware and evidence.
4. Resolve raw time units, state/alarm definitions and temperature validity.
   Celsius conversion is now explicit user policy, not a sensor-validity check.
   Do not infer these remaining semantics from SIP.
5. Initialize credentials and validate one upload when deploying. No GitHub
   origin exists yet; publishing and Supervisor registration remain separate.
6. Multicontroller support requires its own verified map; project scope alone
   does not imply that the existing MINI client supports it.

Canonical working directory is
`C:\Users\Joon\Projects\seas-neg-power-to-influxdb`. The older MINI-named path is
a junction. The original active-thread root contains only the document junction;
execute future development commands with the canonical directory explicitly.
