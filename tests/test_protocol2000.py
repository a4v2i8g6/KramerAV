"""Hardware-free Protocol 2000 tests using a simulated TCP switcher."""
from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "custom_components" / "kramer_av_routing" / "protocol2000.py"
spec = importlib.util.spec_from_file_location("kramer_2000_test_protocol", PATH)
p = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = p
spec.loader.exec_module(p)


class FrameTests(unittest.TestCase):
    def test_encoding(self):
        self.assertEqual(p.encode_frame(1, 5, 8, 3), bytes.fromhex("01 85 88 83"))

    def test_decoding(self):
        self.assertEqual(p.decode_frame(bytes.fromhex("41 85 88 83")), p.Frame2000(1, 5, 8, 3, True))
        self.assertIsNone(p.decode_frame(bytes.fromhex("41 05 88 83")))
        self.assertIsNone(p.decode_frame(bytes.fromhex("41 85 88 80")))

    def test_reject_invalid_command(self):
        with self.assertRaises(ValueError):
            p.encode_frame(64, 2, 3)
        with self.assertRaises(ValueError):
            p.encode_frame(1, 128, 3)
        with self.assertRaises(ValueError):
            p.encode_frame(1, 1, 3, 0)


class _FakeMatrix:
    def __init__(self):
        self.video = {1: 2, 2: 1}
        self.audio = {1: 3, 2: 2}
        self.locked = 0
        self.commands = []

    async def handle(self, reader, writer):
        try:
            while True:
                raw = await reader.readexactly(4)
                msg = p.decode_frame(raw)
                if msg is None:
                    continue
                self.commands.append(msg)
                out, inp = msg.output, msg.input
                if msg.instruction == 62:
                    count = ({1: 4, 2: 2}.get(inp) if out == 1
                             else {1: 3, 2: 2}.get(inp))
                    response = bytes(((62 | 0x40), 0x80 | inp, 0x80 | (count or 0), 0x80 | msg.machine))
                elif msg.instruction in (5, 6):
                    source = (self.video if msg.instruction == 5 else self.audio).get(out, 0)
                    response = bytes((msg.instruction | 0x40, 0x80, 0x80 | source, 0x80 | msg.machine))
                elif msg.instruction in (1, 2):
                    (self.video if msg.instruction == 1 else self.audio)[out] = inp
                    response = bytes((msg.instruction | 0x40, 0x80 | inp, 0x80 | out, 0x80 | msg.machine))
                elif msg.instruction == 31:
                    response = bytes((31 | 0x40, 0x80, 0x80 | self.locked, 0x80 | msg.machine))
                elif msg.instruction == 30:
                    self.locked = inp
                    response = bytes((30 | 0x40, 0x80 | inp, 0x80, 0x80 | msg.machine))
                else:
                    response = bytes((16 | 0x40, 0x80, 0x81, 0x80 | msg.machine))
                # Exercise fragmentation and stray bytes in the TCP reader.
                writer.write(b"\xff" + response[:1]); await writer.drain()
                await asyncio.sleep(0.001)
                writer.write(response[1:]); await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError, BrokenPipeError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()


class AsyncClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.dev = _FakeMatrix()
        self.server = await asyncio.start_server(self.dev.handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]
        self.received = []
        self.client = p.Kramer2000Client("127.0.0.1", self.port, on_message=self.received.append)

    async def asyncTearDown(self):
        await self.client.close()
        self.server.close()
        await self.server.wait_closed()

    async def test_discovery_read_only(self):
        self.assertEqual(await p.probe_protocol2000(self.client), (4, 2))
        self.assertTrue(all(message.instruction == 62 for message in self.dev.commands))

    async def test_video_audio_switch_and_status(self):
        self.assertEqual((await self.client.command(5, 0, 1)).output, 2)
        await self.client.command(1, 4, 1,
                                  matcher=lambda m: m.instruction == 1 and m.input == 4 and m.output == 1)
        self.assertEqual((await self.client.command(5, 0, 1)).output, 4)
        await self.client.command(2, 3, 2)
        self.assertEqual((await self.client.command(6, 0, 2)).output, 3)
        self.assertEqual(len(self.received), 5)

    async def test_front_panel_lock(self):
        self.assertEqual((await self.client.command(31, 0, 0)).output, 0)
        await self.client.command(30, 1, 0)
        self.assertEqual((await self.client.command(31, 0, 0)).output, 1)

    async def test_rejected_command(self):
        with self.assertRaises(p.Protocol2000Error):
            await self.client.command(35, 0, 0)

    async def test_wrong_machine_not_confused(self):
        # Confirm requests address the configured machine without override bit.
        await p.probe_protocol2000(self.client)
        self.assertEqual({x.machine for x in self.dev.commands}, {1})
