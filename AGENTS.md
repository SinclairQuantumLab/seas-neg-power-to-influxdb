# seas-neg-power-to-influxdb

- Use the `to-influxdb-development` skill. Read `.agents/PROVENANCE.md` and
  `.agents/VALIDATION.md` before changes, and the two `device-docs` investigation
  notes before modifying protocol access or interpretation.
- Primary reference: `seas-sip-power-to-influxdb`. Keep `main.py` a direct,
  sequential script; the source client owns TCP framing and register decoding.
- Product scope is NEG POWER; currently implemented model is MINI over TCP only.
  Do not reuse its addresses for multicontroller, LP, hybrid, SMALL, or NIOPS.
- Preserve uncertain semantics as raw fields. No assumed uptime unit, named
  status/alarm bits, sensor validity, serial number, or pressure conversion.
- Device access is FC03 read-only. No heating or configuration writes.
- Credentials belong in the private `imaq-secret` submodule. Never inspect,
  print, copy, or commit credential contents. Dry-run must not load credentials.
- Tests live in `.agents/`, matching the selected SIP repository. Use
  `uv run pytest -q`, `uv run ruff check .`, and `git diff --check`.
- `device-docs/research` contains preserved historical investigation tools,
  excluded from production lint; they are not runtime dependencies.
- Update README/schema and validation evidence with relevant changes. Distinguish
  synthetic/offline checks from actual controller/InfluxDB operation.
