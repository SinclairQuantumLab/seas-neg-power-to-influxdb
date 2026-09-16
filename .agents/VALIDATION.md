# Validation and handoff

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
4. Resolve raw time units, state/alarm definitions and temperature validity before
   exposing normalized versions of those fields. Do not infer them from SIP.
5. Initialize credentials and validate one upload when deploying. No GitHub
   origin exists yet; publishing and Supervisor registration remain separate.
6. Multicontroller support requires its own verified map; project scope alone
   does not imply that the existing MINI client supports it.

Canonical working directory is
`C:\Users\Joon\Projects\seas-neg-power-to-influxdb`. The older MINI-named path is
a junction. The original active-thread root contains only the document junction;
execute future development commands with the canonical directory explicitly.
