"""Asynchronous Kramer Protocol 2000 TCP transport (binary 4-byte frames).

Based on the manufacturer's Protocol 2000 v0.51 documentation. Commands and
replies are serialized; front-panel notifications are delivered separately.
This module never enables all-machine override or changes a device's protocol.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass


class Protocol2000Error(Exception):
    """Protocol communication or command error."""


class Protocol2000Timeout(Protocol2000Error):
    """No reply from a selected machine."""


@dataclass(frozen=True)
class Frame2000:
    instruction: int
    input: int
    output: int
    machine: int
    reply: bool


def encode_frame(instruction: int, input_value: int, output_value: int, machine: int = 1) -> bytes:
    """Encode a command addressed to a single Kramer machine (never broadcast)."""
    if not 0 <= instruction <= 63:
        raise ValueError("Protocol 2000 instruction must be 0..63")
    if not 0 <= input_value <= 127 or not 0 <= output_value <= 127:
        raise ValueError("Protocol 2000 parameters must be 0..127")
    if not 1 <= machine <= 31:
        raise ValueError("Protocol 2000 machine must be 1..31")
    return bytes((instruction, 0x80 | input_value, 0x80 | output_value, 0x80 | machine))


def decode_frame(raw: bytes) -> Frame2000 | None:
    """Reject false frame boundaries, broadcast, invalid machine numbers."""
    if len(raw) != 4 or raw[0] & 0x80 or any((byte & 0x80) == 0 for byte in raw[1:]):
        return None
    machine = raw[3] & 0x1F
    if not machine:
        return None
    return Frame2000(raw[0] & 0x3F, raw[1] & 0x7F, raw[2] & 0x7F,
                     machine, bool(raw[0] & 0x40))


class Kramer2000Client:
    """TCP client with one in-flight request and unsolicited feedback handling."""

    transport = "tcp"

    def __init__(self, host: str, port: int = 5000, machine: int = 1,
                 timeout: float = 4.0,
                 on_message: Callable[[Frame2000], None] | None = None,
                 on_disconnect: Callable[[], None] | None = None) -> None:
        if not 1 <= machine <= 31:
            raise ValueError("Invalid machine ID")
        self.host = host
        self.port = port
        self.machine = machine
        self.timeout = timeout
        self.on_message = on_message
        self.on_disconnect = on_disconnect
        self._writer: asyncio.StreamWriter | None = None
        self._reader_task: asyncio.Task | None = None
        self._connect_lock = asyncio.Lock()
        self._command_lock = asyncio.Lock()
        self._pending: asyncio.Future[Frame2000] | None = None
        self._match: Callable[[Frame2000], bool] | None = None
        self._closing = False

    @property
    def connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    async def connect(self) -> None:
        if self.connected:
            return
        async with self._connect_lock:
            if self.connected:
                return
            self._closing = False
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port), self.timeout)
            except (OSError, asyncio.TimeoutError) as exc:
                raise Protocol2000Error(f"TCP connection failed: {exc}") from exc
            self._writer = writer
            self._reader_task = asyncio.create_task(self._read(reader, writer))

    async def _read(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        data = bytearray()
        try:
            while chunk := await reader.read(4096):
                data.extend(chunk)
                while len(data) >= 4:
                    frame = decode_frame(bytes(data[:4]))
                    if frame is None:
                        del data[0]
                        continue
                    del data[:4]
                    if frame.machine != self.machine or not frame.reply:
                        continue
                    if self.on_message:
                        self.on_message(frame)
                    future = self._pending
                    if future and not future.done():
                        if frame.instruction == 16 and frame.output in (0, 1, 2, 3, 6):
                            # Instruction 16 with output 4/5 is also used as
                            # unsolicited invalid/valid input detection.
                            future.set_exception(Protocol2000Error(f"Device error code {frame.output}"))
                        elif self._match and self._match(frame):
                            future.set_result(frame)
        except (OSError, asyncio.CancelledError):
            pass
        finally:
            if self._writer is writer:
                self._writer = None
                writer.close()
                if self._pending and not self._pending.done():
                    self._pending.set_exception(Protocol2000Error("TCP connection lost"))
                if not self._closing and self.on_disconnect:
                    self.on_disconnect()

    async def command(self, instruction: int, input_value: int, output_value: int,
                      *, matcher: Callable[[Frame2000], bool] | None = None,
                      timeout: float | None = None) -> Frame2000:
        raw = encode_frame(instruction, input_value, output_value, self.machine)
        async with self._command_lock:
            await self.connect()
            future: asyncio.Future[Frame2000] = asyncio.get_running_loop().create_future()
            self._pending = future
            self._match = matcher or (lambda msg: msg.instruction == instruction)
            try:
                if not self._writer:
                    raise Protocol2000Error("TCP connection unavailable")
                self._writer.write(raw)
                await self._writer.drain()
                try:
                    return await asyncio.wait_for(future, self.timeout if timeout is None else timeout)
                except asyncio.TimeoutError as exc:
                    raise Protocol2000Timeout(f"No Protocol 2000 reply to instruction {instruction}") from exc
            except OSError as exc:
                raise Protocol2000Error(f"Socket error: {exc}") from exc
            finally:
                if not future.done():
                    future.cancel()
                self._pending = None
                self._match = None

    async def close(self) -> None:
        self._closing = True
        if self._pending and not self._pending.done():
            self._pending.set_exception(Protocol2000Error("Connection closed"))
        writer, self._writer = self._writer, None
        if writer:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass
        task, self._reader_task = self._reader_task, None
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


async def probe_protocol2000(client: Kramer2000Client) -> tuple[int, int]:
    """Read-only, conservative detection of a video switcher's I/O count.

    Protocol 2000 instruction 62 replies with the requested quantity in OUTPUT.
    No switching, broadcast, reset, or mode change is performed.
    """
    inputs_reply = await client.command(
        62, 1, 1, matcher=lambda m: m.instruction == 62 and m.input == 1)
    outputs_reply = await client.command(
        62, 2, 1, matcher=lambda m: m.instruction == 62 and m.input == 2)
    counts = inputs_reply.output, outputs_reply.output
    if not all(1 <= item <= 127 for item in counts):
        raise Protocol2000Error(f"Unusable Protocol 2000 video I/O counts: {counts}")
    return counts
