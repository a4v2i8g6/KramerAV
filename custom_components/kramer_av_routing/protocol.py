"""Small dependency-free async client for Kramer Protocol 3000.

Supports TCP and UDP. Read-only queries and routing commands use a single
in-flight transaction per connection; unsolicited feedback is delivered to
on_message even while a transaction is running.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import re
from typing import Literal


class KramerError(Exception):
    """Base error for the protocol client."""


class KramerConnectionError(KramerError):
    """The device is disconnected or did not respond."""


class KramerCommandError(KramerError):
    """The device rejected a command."""


@dataclass(frozen=True)
class KramerMessage:
    """A framed device response, e.g. ~01@VID 2>3."""

    command: str
    payload: str
    raw: str


def parse_message(line: str) -> KramerMessage | None:
    """Parse a single Protocol 3000 line, ignoring non-framed chatter."""
    line = line.strip()
    match = re.match(r"^~(?:\d+@)?(?P<body>.+)$", line)
    if not match:
        return None
    body = match.group("body").strip()
    if not body:
        return None
    parts = body.split(maxsplit=1)
    return KramerMessage(parts[0].upper().rstrip("?"), parts[1].strip() if len(parts) == 2 else "", line)


def parse_io_count(message: KramerMessage) -> tuple[int, int] | None:
    """Extract counts from INFO-IO response, if present."""
    if message.command != "INFO-IO":
        return None
    match = re.search(r"\bIN\s+(\d+)\s*,\s*OUT\s+(\d+)\b", message.payload, re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def parse_route(message: KramerMessage, family: str) -> dict[int, int]:
    """Extract output->input mappings for a video routing response."""
    if family == "route" and message.command == "ROUTE":
        # ROUTE layer,destination,source; video layer is 1.
        match = re.fullmatch(r"\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*", message.payload)
        if match and int(match.group(1)) == 1:
            return {int(match.group(2)): int(match.group(3))}
    elif family == "vid" and message.command in ("VID", "AV"):
        # Some models return several routes in one reply.
        return {int(out): int(src) for src, out in re.findall(r"(?<!\w)(\d+)\s*>\s*(\d+)(?!\w)", message.payload)}
    return {}


class _UdpReceiver(asyncio.DatagramProtocol):
    def __init__(self, client: KramerClient) -> None:
        self._client = client

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        for line in re.split(rb"[\r\n]+", data):
            if line:
                self._client._handle_line(line.decode("ascii", errors="replace"))

    def error_received(self, exc: Exception) -> None:
        self._client._fail_pending(KramerConnectionError(f"UDP socket error: {exc}"))

    def connection_lost(self, exc: Exception | None) -> None:
        self._client._udp_transport = None
        self._client._fail_pending(KramerConnectionError("UDP socket closed"))
        self._client._notify_connection_change()


class KramerClient:
    """Async TCP/UDP Protocol 3000 command client.

    Replies are matched by command and an optional caller-provided predicate.
    All routing replies (including spontaneous front-panel updates) are
    forwarded to on_message. No write command is sent during probing.
    """

    def __init__(
        self,
        host: str,
        port: int,
        transport: Literal["tcp", "udp"] = "tcp",
        timeout: float = 4.0,
        on_message: Callable[[KramerMessage], None] | None = None,
        on_disconnect: Callable[[], None] | None = None,
    ) -> None:
        if transport not in ("tcp", "udp"):
            raise ValueError("Transport must be tcp or udp")
        self.host = host
        self.port = port
        self.transport = transport
        self.timeout = timeout
        self.on_message = on_message
        self.on_disconnect = on_disconnect
        self._reader_task: asyncio.Task | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._udp_transport: asyncio.DatagramTransport | None = None
        self._command_lock = asyncio.Lock()
        self._connect_lock = asyncio.Lock()
        self._pending: asyncio.Future[KramerMessage] | None = None
        self._pending_key: str | None = None
        self._pending_matcher: Callable[[KramerMessage], bool] | None = None
        self._closing = False

    @property
    def connected(self) -> bool:
        if self.transport == "udp":
            return self._udp_transport is not None and not self._udp_transport.is_closing()
        return self._writer is not None and not self._writer.is_closing()

    async def connect(self) -> None:
        """Open socket if necessary. For UDP this is not a reachability check."""
        if self.connected:
            return
        async with self._connect_lock:
            if self.connected:
                return
            self._closing = False
            try:
                if self.transport == "tcp":
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(self.host, self.port), timeout=self.timeout
                    )
                    self._writer = writer
                    self._reader_task = asyncio.create_task(self._read_tcp(reader, writer))
                else:
                    loop = asyncio.get_running_loop()
                    transport, _ = await asyncio.wait_for(
                        loop.create_datagram_endpoint(
                            lambda: _UdpReceiver(self),
                            remote_addr=(self.host, self.port),
                        ),
                        timeout=self.timeout,
                    )
                    self._udp_transport = transport
            except (OSError, asyncio.TimeoutError) as exc:
                raise KramerConnectionError(f"Cannot connect to {self.host}:{self.port}: {exc}") from exc

    async def close(self) -> None:
        """Shut down the transport and any pending transaction."""
        self._closing = True
        self._fail_pending(KramerConnectionError("Connection closed"))
        writer, self._writer = self._writer, None
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass
        task, self._reader_task = self._reader_task, None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        transport, self._udp_transport = self._udp_transport, None
        if transport is not None:
            transport.close()

    async def _read_tcp(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        buffer = b""
        try:
            while True:
                chunk = await reader.read(4096)
                if not chunk:
                    break
                buffer += chunk
                if len(buffer) > 65536:
                    # Avoid unbounded memory use from a misbehaving peer.
                    buffer = buffer[-4096:]
                pieces = re.split(rb"[\r\n]+", buffer)
                buffer = pieces.pop()
                for item in pieces:
                    if item:
                        self._handle_line(item.decode("ascii", errors="replace"))
        except (OSError, asyncio.CancelledError):
            pass
        finally:
            if self._writer is writer:
                self._writer = None
                writer.close()
                self._fail_pending(KramerConnectionError("TCP connection lost"))
                self._notify_connection_change()

    def _fail_pending(self, error: Exception) -> None:
        if self._pending is not None and not self._pending.done():
            self._pending.set_exception(error)

    def _notify_connection_change(self) -> None:
        if not self._closing and self.on_disconnect:
            self.on_disconnect()

    def _handle_line(self, line: str) -> None:
        message = parse_message(line)
        if message is None:
            return
        if self.on_message:
            self.on_message(message)
        if self._pending is None or self._pending.done():
            return
        # Some Kramer firmware reports an AV acknowledgment after a VID route
        # when audio-follow-video is active.
        if message.command != self._pending_key and not (
            self._pending_key == "VID" and message.command == "AV"
        ):
            return
        if re.search(r"\bERR\s*\d+\b", message.payload, re.IGNORECASE):
            self._pending.set_exception(KramerCommandError(message.raw))
            return
        if self._pending_matcher is None or self._pending_matcher(message):
            self._pending.set_result(message)

    async def command(
        self,
        command: str,
        matcher: Callable[[KramerMessage], bool] | None = None,
    ) -> KramerMessage:
        """Send #COMMAND<CR> and await its framed response."""
        if not re.fullmatch(r"[A-Za-z0-9-]+\??(?: [A-Za-z0-9_,.>*-]+)?", command):
            raise ValueError("Invalid Protocol 3000 command syntax")
        async with self._command_lock:
            await self.connect()
            loop = asyncio.get_running_loop()
            future: asyncio.Future[KramerMessage] = loop.create_future()
            self._pending = future
            self._pending_key = command.split(" ", 1)[0].upper().rstrip("?")
            self._pending_matcher = matcher
            try:
                payload = f"#{command}\r".encode("ascii")
                if self.transport == "tcp":
                    if self._writer is None:
                        raise KramerConnectionError("TCP connection is not open")
                    self._writer.write(payload)
                    await self._writer.drain()
                else:
                    if self._udp_transport is None:
                        raise KramerConnectionError("UDP socket is not open")
                    self._udp_transport.sendto(payload)
                try:
                    return await asyncio.wait_for(future, timeout=self.timeout)
                except asyncio.TimeoutError as exc:
                    raise KramerConnectionError(f"No response to {command}") from exc
            except OSError as exc:
                raise KramerConnectionError(str(exc)) from exc
            finally:
                if not future.done():
                    future.cancel()
                self._pending = None
                self._pending_key = None
                self._pending_matcher = None
