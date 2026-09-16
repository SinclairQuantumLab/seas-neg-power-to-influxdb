"""Read NEG POWER MINI holding registers using the recovered vendor Manager map."""

from __future__ import annotations

import math
import socket
import struct
import time
from dataclasses import dataclass
from datetime import UTC, datetime

DEFAULT_PORT = 502


class SAESNEGPowerMiniError(RuntimeError):
    """Report a failed read; no partial sample is returned and no retry is hidden."""


class SAESNEGPowerMiniCommunicationError(SAESNEGPowerMiniError):
    """Report a connection, timeout, or truncated TCP response failure."""


class SAESNEGPowerMiniProtocolError(SAESNEGPowerMiniError):
    """Report a mismatched response or a controller Modbus exception."""


@dataclass(frozen=True)
class SAESNEGPowerMiniSettings:
    """Specify one MINI endpoint and its explicitly configured Modbus unit ID.

    No connection is opened by this value object. ``timeout_s`` bounds a TCP
    connection attempt or one complete request, including fragmented responses.
    The unit ID has no assumed device default; read it from the controller.
    """

    host: str
    unit_id: int
    port: int = DEFAULT_PORT
    timeout_s: float = 3.0


@dataclass(frozen=True)
class SourceSample:
    """Hold one successful MINI poll, stamped after its final response in UTC.

    Several FC03 requests make up this poll; it is not an atomic hardware
    snapshot. Raw fields preserve unresolved state, alarm, sensor-validity,
    version, and time semantics. Electrical floats reproduce Manager rounding,
    not a claim about instrument accuracy. ``work_time_s`` is absent on firmware
    values <= 0x200. No serial number is known from the recovered map.
    """

    observed_at: datetime
    software_version_raw: int
    hardware_revision: str
    status_raw: int
    usb_logging_status_raw: int
    uptime_raw: int
    internal_temperature_k: int
    pump_temperature_raw: int
    output_voltage_raw: int
    output_current_raw: int
    output_voltage_v: float
    output_current_a: float
    active_time_raw: int
    alarm_flags_raw: int
    temperature_error_flags_raw: int
    work_time_s: int | None


def _uint32(words: list[int], offset: int) -> int:
    """Combine the vendor's low-address low word and following high word."""
    return words[offset] | (words[offset + 1] << 16)


class SAESNEGPowerMiniClient:
    """Own one synchronous TCP connection for read-only MINI polling.

    Call ``connect`` before ``read_sample`` and ``close`` when finished. This
    class implements only FC03 at fixed, recovered MINI addresses; it cannot
    start heating, stop heating, change settings, or reset alarms. It is not
    thread-safe and must not share a connection between concurrent callers.

    On communication/protocol failure it drops the connection and raises a
    source error. The caller owns retry policy; ``reconnect`` closes and opens
    a fresh socket. Firmware identity is read again for every poll, so extension
    reads never depend on a stale cached version. Other NEG POWER models and
    RTU are not implemented. See device-docs/NEG-POWER-MINI-MODBUS.md for evidence
    and remaining hardware-validation requirements.
    """

    def __init__(self, settings: SAESNEGPowerMiniSettings) -> None:
        """Store endpoint settings and validate framing/timeout preconditions."""
        if not 0 <= settings.unit_id <= 255:
            raise ValueError("Modbus TCP unit_id must fit in one byte")
        if not math.isfinite(settings.timeout_s) or settings.timeout_s <= 0:
            raise ValueError("timeout_s must be finite and positive")
        self.settings = settings
        self._socket: socket.socket | None = None
        self._transaction_id = 0

    @property
    def is_connected(self) -> bool:
        """Report socket ownership; peer health is checked by the next read."""
        return self._socket is not None

    def connect(self) -> None:
        """Open the configured TCP endpoint unless already connected."""
        if self._socket is not None:
            return
        try:
            self._socket = socket.create_connection(
                (self.settings.host, self.settings.port), self.settings.timeout_s
            )
        except OSError as ex:
            raise SAESNEGPowerMiniCommunicationError(
                f"Cannot connect to MINI: {ex}"
            ) from ex

    def close(self) -> None:
        """Release the owned socket; repeated calls are harmless."""
        connection, self._socket = self._socket, None
        if connection is not None:
            connection.close()

    def reconnect(self) -> None:
        """Replace the connection without changing any controller setting."""
        self.close()
        self.connect()

    def _recv_exact(self, count: int, deadline: float) -> bytes:
        """Receive a bounded frame portion despite TCP fragmentation."""
        if self._socket is None:
            raise SAESNEGPowerMiniCommunicationError("MINI is not connected")
        result = bytearray()
        while len(result) < count:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Modbus response deadline exceeded")
            self._socket.settimeout(remaining)
            chunk = self._socket.recv(count - len(result))
            if not chunk:
                raise SAESNEGPowerMiniCommunicationError("Truncated Modbus response")
            result.extend(chunk)
        return bytes(result)

    def _read_holding_registers(self, address: int, count: int) -> list[int]:
        """Send one FC03 request and validate its MBAP header and exact word count."""
        if self._socket is None:
            raise SAESNEGPowerMiniCommunicationError("MINI is not connected")
        self._transaction_id = (self._transaction_id + 1) & 0xFFFF
        request = struct.pack(
            ">HHHBBHH",
            self._transaction_id,
            0,
            6,
            self.settings.unit_id,
            3,
            address,
            count,
        )
        deadline = time.monotonic() + self.settings.timeout_s
        try:
            self._socket.settimeout(self.settings.timeout_s)
            self._socket.sendall(request)
            transaction, protocol, length, unit = struct.unpack(
                ">HHHB", self._recv_exact(7, deadline)
            )
            if (transaction, protocol, unit) != (
                self._transaction_id,
                0,
                self.settings.unit_id,
            ):
                raise SAESNEGPowerMiniProtocolError("Mismatched Modbus response header")
            # Length includes the unit byte already consumed in the MBAP header.
            if length not in (3, 3 + 2 * count):
                raise SAESNEGPowerMiniProtocolError("Invalid Modbus response length")
            pdu = self._recv_exact(length - 1, deadline)
            if pdu[0] == 0x83 and len(pdu) == 2:
                raise SAESNEGPowerMiniProtocolError(
                    f"FC03 at 0x{address:04x}: Modbus exception 0x{pdu[1]:02x}"
                )
            if pdu[:2] != bytes((3, 2 * count)) or len(pdu) != 2 + 2 * count:
                raise SAESNEGPowerMiniProtocolError("Invalid FC03 response payload")
            return list(struct.unpack(f">{count}H", pdu[2:]))
        except (OSError, SAESNEGPowerMiniError) as ex:
            self.close()
            if isinstance(ex, SAESNEGPowerMiniError):
                raise
            raise SAESNEGPowerMiniCommunicationError(
                f"FC03 at 0x{address:04x} failed: {ex}"
            ) from ex

    def read_sample(self) -> SourceSample:
        """Read identity, status, and firmware-gated work time as one poll.

        Electrical values use the vendor's positive half-up rounding to 0.1 V/A.
        Pump temperature is retained only as a raw register: an absent/broken
        thermocouple must not silently become a physical temperature field.
        Failure of any block rejects the entire poll; no old block is reused.
        """
        identity = self._read_holding_registers(0x1000, 3)
        version = _uint32(identity, 0)
        status = self._read_holding_registers(0x2000, 14)
        work_time_s = None
        if version > 0x200:
            work_time_s = _uint32(self._read_holding_registers(0x200E, 2), 0)
        return SourceSample(
            observed_at=datetime.now(UTC),
            software_version_raw=version,
            hardware_revision=f"{identity[2] >> 8}.{identity[2] & 0xFF}",
            status_raw=status[0],
            usb_logging_status_raw=status[1],
            uptime_raw=_uint32(status, 2),
            internal_temperature_k=status[4],
            pump_temperature_raw=status[5],
            output_voltage_raw=status[6],
            output_current_raw=status[7],
            output_voltage_v=((status[6] + 5) // 10) / 10.0,
            output_current_a=((status[7] + 5) // 10) / 10.0,
            active_time_raw=_uint32(status, 8),
            alarm_flags_raw=_uint32(status, 10),
            temperature_error_flags_raw=_uint32(status, 12),
            work_time_s=work_time_s,
        )
