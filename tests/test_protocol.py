"""Protocol tests run without Home Assistant or any Kramer hardware."""

import asyncio
import importlib.util
from pathlib import Path
import sys
import unittest

PATH = Path(__file__).resolve().parents[1] / "custom_components" / "kramer_av_routing" / "protocol.py"
spec = importlib.util.spec_from_file_location("kramer_p3000_test_protocol", PATH)
protocol = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = protocol
spec.loader.exec_module(protocol)


class ParsingTest(unittest.TestCase):
    def test_model(self):
        msg = protocol.parse_message("~01@MODEL VP-778\r\n")
        self.assertEqual(msg.command, "MODEL")
        self.assertEqual(msg.payload, "VP-778")

    def test_io_count_with_question_mark(self):
        msg = protocol.parse_message("~01@INFO-IO? IN 8,OUT 4")
        self.assertEqual(protocol.parse_io_count(msg), (8, 4))

    def test_routes(self):
        self.assertEqual(
            protocol.parse_route(protocol.parse_message("~01@ROUTE 1,3,2"), "route"),
            {3: 2},
        )
        self.assertEqual(
            protocol.parse_route(protocol.parse_message("~01@VID 1>1,2>2,0>3"), "vid"),
            {1: 1, 2: 2, 3: 0},
        )
        self.assertEqual(
            protocol.parse_route(protocol.parse_message("~01@ROUTE 2,1,4"), "route"),
            {},
        )

    def test_afv_feedback(self):
        self.assertEqual(
            protocol.parse_route(protocol.parse_message("~01@AV 3>1"), "vid"),
            {1: 3},
        )

    def test_garbage(self):
        self.assertIsNone(protocol.parse_message("NOT A KRAMER MESSAGE"))


class _UdpDevice(asyncio.DatagramProtocol):
    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, address):
        command = data.decode().strip()
        replies = {"#MODEL?": "~01@MODEL VS-44DT\r\n", "#VID? 1": "~01@VID 2>1\r\n"}
        if command in replies:
            self.transport.sendto(replies[command].encode(), address)


class AsyncProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.received = []
        self.server = await asyncio.start_server(self._tcp_device, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()

    async def _tcp_device(self, reader, writer):
        try:
            while command := await reader.readuntil(b"\r"):
                value = command.decode().strip()
                if value == "#MODEL?":
                    writer.write(b"~01@MODEL VS-88H2A\r\n")
                elif value == "#INFO-IO?":
                    writer.write(b"~01@INFO-IO? IN 8,OUT 8\r\n")
                elif value == "#ROUTE? 1,1":
                    # An unrelated change shouldn't satisfy a query for output 1.
                    writer.write(b"~01@ROUTE 1,2,3\r\n~01@ROUTE 1,1,5\r\n")
                elif value == "#ROUTE 1,1,2":
                    writer.write(b"~01@ROUTE 1,1,2\r\n")
                elif value == "#VID? 1":
                    writer.write(b"~01@VID ERR003\r\n")
                elif value == "#VID 2>3":
                    writer.write(b"~01@AV 2>3\r\n")
                await writer.drain()
        except asyncio.IncompleteReadError:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_tcp_with_unsolicited_and_matcher(self):
        client = protocol.KramerClient("127.0.0.1", self.port, on_message=self.received.append)
        try:
            model = await client.command("MODEL?")
            self.assertEqual(model.payload, "VS-88H2A")
            counts = protocol.parse_io_count(await client.command("INFO-IO?"))
            self.assertEqual(counts, (8, 8))
            reply = await client.command("ROUTE? 1,1", matcher=lambda m: 1 in protocol.parse_route(m, "route"))
            self.assertEqual(protocol.parse_route(reply, "route"), {1: 5})
            self.assertIn(2, [list(protocol.parse_route(m, "route"))[0] for m in self.received if protocol.parse_route(m, "route")])
            self.assertEqual((await client.command("ROUTE 1,1,2")).payload, "1,1,2")
        finally:
            await client.close()

    async def test_error_reply(self):
        client = protocol.KramerClient("127.0.0.1", self.port)
        try:
            with self.assertRaises(protocol.KramerCommandError):
                await client.command("VID? 1")
        finally:
            await client.close()

    async def test_afv_ack(self):
        client = protocol.KramerClient("127.0.0.1", self.port)
        try:
            reply = await client.command("VID 2>3")
            self.assertEqual(protocol.parse_route(reply, "vid"), {3: 2})
        finally:
            await client.close()

    async def test_udp(self):
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(lambda: _UdpDevice(), local_addr=("127.0.0.1", 0))
        port = transport.get_extra_info("sockname")[1]
        client = protocol.KramerClient("127.0.0.1", port, transport="udp")
        try:
            self.assertEqual((await client.command("MODEL?")).payload, "VS-44DT")
            self.assertEqual((await client.command("VID? 1")).payload, "2>1")
        finally:
            await client.close()
            transport.close()


if __name__ == "__main__":
    unittest.main()
