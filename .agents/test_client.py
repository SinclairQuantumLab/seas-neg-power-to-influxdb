"""Offline protocol tests; all register values are synthetic, not hardware captures."""

import socket
import struct
import threading
from datetime import UTC

import pytest

import saes_neg_power_mini_client as source

STATUS = [
    4,
    2,
    0x5678,
    0x1234,
    300,
    65535,
    1234,
    456,
    0xABCD,
    0x1234,
    0xFF00,
    0x8000,
    2,
    1,
]


def frame(transaction: int, words: list[int], unit: int = 7) -> bytes:
    """Encode a synthetic server reply in standard big-endian register order."""
    return struct.pack(
        f">HHHBBB{len(words)}H",
        transaction,
        0,
        3 + 2 * len(words),
        unit,
        3,
        2 * len(words),
        *words,
    )


class FakeSocket:
    """Deliver one-byte fragments or injected errors without opening a network."""

    def __init__(self, reply: bytes, error: OSError | None = None) -> None:
        """Queue reply bytes and collect emitted requests."""
        self.reply = bytearray(reply)
        self.error = error
        self.requests: list[bytes] = []
        self.closed = False

    def settimeout(self, value: float) -> None:
        """Check that every operation has a positive timeout."""
        assert value > 0

    def sendall(self, data: bytes) -> None:
        """Capture the complete request without adding an implicit response."""
        self.requests.append(data)

    def recv(self, count: int) -> bytes:
        """Fragment the input regardless of the caller's requested byte count."""
        if self.error:
            raise self.error
        assert count > 0
        result = bytes(self.reply[:1])
        del self.reply[:1]
        return result

    def close(self) -> None:
        """Record socket release."""
        self.closed = True


def client_with(
    monkeypatch: pytest.MonkeyPatch,
    sock: FakeSocket,
) -> source.SAESNEGPowerMiniClient:
    """Connect the production client to a synthetic TCP byte stream."""
    monkeypatch.setattr(socket, "create_connection", lambda *args: sock)
    client = source.SAESNEGPowerMiniClient(
        source.SAESNEGPowerMiniSettings("controller.invalid", unit_id=7)
    )
    client.connect()
    return client


@pytest.mark.parametrize("version", [0x1FF, 0x200, 0x201])
def test_vendor_map_and_version_gate(
    monkeypatch: pytest.MonkeyPatch,
    version: int,
) -> None:
    """Check exact FC03 wire addresses, word order, rounding and extension gating."""
    response = frame(1, [version, 0, 0x0102]) + frame(2, STATUS)
    if version > 0x200:
        response += frame(3, [0x5678, 0x1234])
    sock = FakeSocket(response)
    client = client_with(monkeypatch, sock)
    sample = client.read_sample()
    assert sock.requests[:2] == [
        bytes.fromhex("0001 0000 0006 07 03 1000 0003"),
        bytes.fromhex("0002 0000 0006 07 03 2000 000e"),
    ]
    assert len(sock.requests) == (3 if version > 0x200 else 2)
    if version > 0x200:
        assert sock.requests[2] == bytes.fromhex("0003 0000 0006 07 03 200e 0002")
        assert sample.work_time_s == 0x12345678
    else:
        assert sample.work_time_s is None
    assert sample.hardware_revision == "1.2"
    assert sample.uptime_raw == 0x12345678
    assert sample.active_time_raw == 0x1234ABCD
    assert sample.alarm_flags_raw == 0x8000FF00
    assert sample.temperature_error_flags_raw == 0x00010002
    assert sample.internal_temperature_k == 300
    assert sample.pump_temperature_raw == 65535
    assert sample.output_voltage_v == 12.3
    assert sample.output_current_a == 4.6
    assert sample.observed_at.tzinfo is UTC
    client.close()
    client.close()
    assert sock.closed and not client.is_connected


@pytest.mark.parametrize(
    "raw, expected",
    [(0, 0.0), (4, 0.0), (5, 0.1), (14, 0.1), (15, 0.2), (65535, 655.4)],
)
def test_vendor_rounding(
    monkeypatch: pytest.MonkeyPatch,
    raw: int,
    expected: float,
) -> None:
    """Preserve positive half-up behavior, including ties and register endpoints."""
    status = STATUS.copy()
    status[6:8] = [raw, raw]
    client = client_with(
        monkeypatch, FakeSocket(frame(1, [512, 0, 0]) + frame(2, status))
    )
    sample = client.read_sample()
    assert sample.output_voltage_raw == sample.output_current_raw == raw
    assert sample.output_voltage_v == sample.output_current_a == expected


@pytest.mark.parametrize(
    "reply",
    [
        bytes.fromhex("0002 0000 0009 07 03 06 0200 0000 0102"),  # wrong transaction
        bytes.fromhex("0001 0001 0009 07 03 06 0200 0000 0102"),  # wrong protocol
        bytes.fromhex("0001 0000 0009 08 03 06 0200 0000 0102"),  # wrong unit
        bytes.fromhex("0001 0000 ffff 07"),  # oversized length
        bytes.fromhex("0001 0000 0009 07 04 06 0200 0000 0102"),  # wrong function
        bytes.fromhex("0001 0000 0009 07 03 04 0200 0000 0102"),  # wrong byte count
        bytes.fromhex("0001 0000 0003 07 83 02"),  # device exception
    ],
)
def test_malformed_response_drops_connection(
    monkeypatch: pytest.MonkeyPatch,
    reply: bytes,
) -> None:
    """Reject mismatched/error frames before a sample can be uploaded."""
    sock = FakeSocket(reply)
    client = client_with(monkeypatch, sock)
    with pytest.raises(source.SAESNEGPowerMiniProtocolError):
        client.read_sample()
    assert sock.closed and not client.is_connected


@pytest.mark.parametrize("error", [None, TimeoutError("synthetic timeout")])
def test_truncation_and_timeout(
    monkeypatch: pytest.MonkeyPatch,
    error: OSError | None,
) -> None:
    """Discard a stream that ends early or times out."""
    sock = FakeSocket(b"\x00\x01", error)
    client = client_with(monkeypatch, sock)
    with pytest.raises(source.SAESNEGPowerMiniCommunicationError):
        client.read_sample()
    assert sock.closed


def test_extension_failure_rejects_whole_poll(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never return old status if the required new-firmware block fails."""
    sock = FakeSocket(
        frame(1, [513, 0, 0])
        + frame(2, STATUS)
        + bytes.fromhex("0003 0000 0003 07 83 02")
    )
    client = client_with(monkeypatch, sock)
    with pytest.raises(source.SAESNEGPowerMiniProtocolError, match="0x200e"):
        client.read_sample()
    assert sock.closed


def test_connection_failure_and_reconnect(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fresh socket replaces the old one; connection errors remain source errors."""
    first, second = FakeSocket(b""), FakeSocket(b"")
    client = client_with(monkeypatch, first)
    monkeypatch.setattr(socket, "create_connection", lambda *args: second)
    client.reconnect()
    assert first.closed and client.is_connected
    client.close()

    def unavailable(*args: object) -> socket.socket:
        """Simulate a refused TCP endpoint."""
        raise ConnectionRefusedError("synthetic refusal")

    monkeypatch.setattr(socket, "create_connection", unavailable)
    with pytest.raises(source.SAESNEGPowerMiniCommunicationError):
        client.connect()
    assert not client.is_connected


def test_fragment_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Slow fragments cannot restart the timeout indefinitely."""
    sock = FakeSocket(frame(1, [512, 0, 0]))
    client = client_with(monkeypatch, sock)
    ticks = iter([0.0, 1.0, 4.0])
    monkeypatch.setattr(source.time, "monotonic", lambda: next(ticks))
    with pytest.raises(source.SAESNEGPowerMiniCommunicationError):
        client.read_sample()
    assert sock.closed


def test_real_tcp_loopback() -> None:
    """Exercise real socket I/O against a local FC03 server, never lab hardware."""
    requests: list[bytes] = []
    errors: list[Exception] = []
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        server.settimeout(3)

        def serve() -> None:
            """Handle exactly the three expected read-only MINI requests."""
            try:
                connection, _ = server.accept()
                with connection:
                    connection.settimeout(3)
                    replies = [
                        frame(1, [513, 0, 0x0102]),
                        frame(2, STATUS),
                        frame(3, [7201, 0]),
                    ]
                    for reply in replies:
                        request = bytearray()
                        while len(request) < 12:
                            chunk = connection.recv(12 - len(request))
                            if not chunk:
                                raise EOFError(
                                    "Client closed before completing request"
                                )
                            request.extend(chunk)
                        requests.append(bytes(request))
                        connection.sendall(reply[:4])
                        connection.sendall(reply[4:])
            except Exception as ex:
                errors.append(ex)

        worker = threading.Thread(target=serve, daemon=True)
        worker.start()
        client = source.SAESNEGPowerMiniClient(
            source.SAESNEGPowerMiniSettings(
                "127.0.0.1",
                unit_id=7,
                port=server.getsockname()[1],
                timeout_s=3,
            )
        )
        try:
            client.connect()
            sample = client.read_sample()
            assert sample.work_time_s == 7201
            assert sample.output_current_a == 4.6
        finally:
            client.close()
            worker.join(timeout=4)
        assert not worker.is_alive() and not errors
        assert requests == [
            bytes.fromhex("0001 0000 0006 07 03 1000 0003"),
            bytes.fromhex("0002 0000 0006 07 03 2000 000e"),
            bytes.fromhex("0003 0000 0006 07 03 200e 0002"),
        ]
