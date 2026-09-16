"""Execute the actual relay with synthetic source, clock, and InfluxDB boundaries."""

import runpy
import signal
import sys
import threading
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import influxdb_client
import pytest

import saes_neg_power_mini_client as source

SCRIPT = Path(__file__).resolve().parents[1] / "main.py"
SAMPLE = source.SourceSample(
    datetime(2026, 9, 15, tzinfo=UTC),
    512,
    "1.2",
    4,
    2,
    123,
    300,
    273,
    1234,
    456,
    12.3,
    4.6,
    456,
    0x80000001,
    1,
    None,
)


class FakeClient:
    """Queue whole-poll results and observe the relay's recovery/cleanup policy."""

    def __init__(self, outcomes: list[source.SourceSample | Exception]) -> None:
        """Store synthetic outcomes and lifecycle counters."""
        self.outcomes = outcomes
        self.is_connected = False
        self.reconnections = 0
        self.closed = False

    def connect(self) -> None:
        """Mark the fake source connected."""
        self.is_connected = True

    def reconnect(self) -> None:
        """Count whole-connection replacement."""
        self.reconnections += 1
        self.connect()

    def read_sample(self) -> source.SourceSample:
        """Return or raise the next synthetic outcome."""
        result = self.outcomes.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def close(self) -> None:
        """Record release of the source boundary."""
        self.closed = True


def run_relay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    client: FakeClient,
    *,
    dry_run: bool = False,
    once: bool = True,
    fail_write: bool = False,
) -> tuple[int, list[dict[str, object]], list[str]]:
    """Run main.py in a temporary deployment without reading real credentials."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "settings.toml").write_text(
        'host="controller.invalid"\nunit_id=7\ninterval_s=30\ntimeout_s=3\n'
    )
    records: list[dict[str, object]] = []
    closed: list[str] = []

    def write(**kwargs: object) -> None:
        """Capture a write, or model an unavailable InfluxDB server."""
        if fail_write:
            raise RuntimeError("synthetic write failure")
        assert kwargs["bucket"] == "test-bucket"
        records.extend(kwargs["record"])

    def influx_factory(**kwargs: object) -> SimpleNamespace:
        """Provide synthetic write and cleanup resources, forbidden in dry-run."""
        assert not dry_run
        assert kwargs["url"] == "http://influx.invalid"
        return SimpleNamespace(
            write_api=lambda **kw: SimpleNamespace(
                write=write, close=lambda: closed.append("writer")
            ),
            close=lambda: closed.append("influx"),
        )

    if not dry_run:
        (tmp_path / "imaq-secret").mkdir()
        (tmp_path / "imaq-secret" / "auth.toml").write_text(
            '[influxdb]\nurl="http://influx.invalid"\n'
            'token="SYNTHETIC"\norg="test-org"\nbucket="test-bucket"\n'
        )
    monkeypatch.setattr(influxdb_client, "InfluxDBClient", influx_factory)
    monkeypatch.setattr(source, "SAESNEGPowerMiniClient", lambda settings: client)
    waits: list[float] = []
    monkeypatch.setattr(
        threading,
        "Event",
        lambda: SimpleNamespace(
            is_set=lambda: len(waits) >= 8,
            set=lambda: None,
            wait=lambda seconds: waits.append(seconds),
        ),
    )
    monkeypatch.setattr(signal, "signal", lambda *args: None)
    args = [str(SCRIPT), "--settings", str(tmp_path / "settings.toml")]
    if once:
        args.append("--once")
    if dry_run:
        args.append("--dry-run")
    monkeypatch.setattr(sys, "argv", args)
    try:
        runpy.run_path(str(SCRIPT), run_name="__main__")
        code = 0
    except SystemExit as ex:
        code = ex.code
    return code, records, closed


def test_schema_and_cleanup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Check endpoint/channel identity and avoid interpreting unverified fields."""
    client = FakeClient([SAMPLE])
    code, records, closed = run_relay(monkeypatch, tmp_path, client)
    assert code == 0 and client.closed and closed == ["writer", "influx"]
    record = records[0]
    assert record["measurement"] == "seas-neg-power"
    assert record["tags"] == {
        "source": "SAES NEG POWER MINI",
        "host": "controller.invalid",
        "port": "502",
        "ModbusID": "7",
        "Channel": "1",
    }
    assert record["time"] == SAMPLE.observed_at
    assert record["fields"] == {
        "SoftwareVersionRaw": 512,
        "HardwareRevision": "1.2",
        "StatusRaw": 4,
        "Status": "Steady",
        "USBLoggingStatusRaw": 2,
        "UptimeRaw": 123,
        "InternalTemperature[°C]": 26.85,
        "PumpTemperature[°C]": -0.15,
        "PumpTemperatureRaw": 273,
        "OutputVoltageRaw": 1234,
        "OutputCurrentRaw": 456,
        "OutputVoltage[V]": 12.3,
        "OutputCurrent[A]": 4.6,
        "ActiveTimeRaw": 456,
        "AlarmFlagsRaw": 0x80000001,
        "TemperatureErrorFlagsRaw": 1,
    }
    wire = influxdb_client.Point.from_dict(record).to_line_protocol()
    assert "OutputCurrent[A]=4.6" in wire and "PumpTemperatureRaw=273i" in wire
    assert "PumpTemperature[°C]=-0.15" in wire
    assert "InternalTemperature[°C]=26.85" in wire
    assert 'Status="Steady"' in wire
    assert "Uptime[s]=123, Status=Steady, PumpTemperature[°C]=-0.15" in capsys.readouterr().out
    assert "Pressure" not in wire and "Serial" not in wire


def test_unknown_status_preserves_raw(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Omit unknown status text while still uploading the raw code and readings."""
    client = FakeClient([replace(SAMPLE, status_raw=6)])
    code, records, _ = run_relay(monkeypatch, tmp_path, client)
    assert code == 0
    assert "Status" not in records[0]["fields"]
    assert records[0]["fields"]["StatusRaw"] == 6
    assert records[0]["fields"]["PumpTemperature[°C]"] == -0.15


def test_dry_run_needs_no_auth(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A dry-run works without a credential folder or InfluxDB construction."""
    client = FakeClient([SAMPLE])
    code, records, closed = run_relay(monkeypatch, tmp_path, client, dry_run=True)
    assert code == 0 and client.closed and not records and not closed
    assert not (tmp_path / "imaq-secret").exists()


def test_retry_once(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A failed poll reconnects once and uploads only its successful replacement."""
    client = FakeClient([RuntimeError("first poll failed"), SAMPLE])
    code, records, _ = run_relay(monkeypatch, tmp_path, client)
    assert code == 0 and len(records) == 1 and client.reconnections == 1


def test_lifetime_threshold(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Successful intervening cycles do not reset the three-failure budget."""
    error = RuntimeError("synthetic source failure")
    client = FakeClient([error, error, SAMPLE, error, error, SAMPLE, error, error])
    code, records, closed = run_relay(monkeypatch, tmp_path, client, once=False)
    assert code == 1 and len(records) == 2 and client.reconnections == 3
    assert client.closed and closed == ["writer", "influx"]


def test_write_failure_does_not_retry_source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Fail a one-shot upload without rereading the instrument or leaking handles."""
    client = FakeClient([SAMPLE])
    code, records, closed = run_relay(monkeypatch, tmp_path, client, fail_write=True)
    assert code == 1 and not records and client.reconnections == 0
    assert client.closed and closed == ["writer", "influx"]
