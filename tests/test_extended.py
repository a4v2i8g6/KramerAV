"""Extended routing protocol tests; no Home Assistant or hardware needed."""

import asyncio
import importlib.util
from pathlib import Path
import sys
import unittest

PATH = Path(__file__).resolve().parents[1] / 'custom_components' / 'kramer_av_routing' / 'protocol.py'
spec = importlib.util.spec_from_file_location('kramer_test_extended_protocol', PATH)
protocol = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = protocol
spec.loader.exec_module(protocol)


class ExtendedParsingTest(unittest.TestCase):
    def test_mixed_physical_ports_and_non_video_signals(self):
        msg = protocol.parse_message(
            '~01@SIGNALS-LIST [IN.HDMI.1.VIDEO.1,IN.HDMI.2.VIDEO.1,'
            'IN.HDBT.1.VIDEO.1,OUT.HDBT.4.VIDEO.1,OUT.HDMI.1.VIDEO.1,'
            'IN.HDMI.1.AUDIO.1,OUT.ANALOG_AUDIO.1.AUDIO.1]'
        )
        signals = protocol.parse_signals_list(msg)
        inputs = [s for s in signals if s.direction == 'IN' and s.signal_type == 'VIDEO']
        outputs = [s for s in signals if s.direction == 'OUT' and s.signal_type == 'VIDEO']
        self.assertEqual([str(s) for s in inputs], [
            'IN.HDMI.1.VIDEO.1', 'IN.HDMI.2.VIDEO.1', 'IN.HDBT.1.VIDEO.1'])
        self.assertEqual([str(s) for s in outputs], [
            'OUT.HDBT.4.VIDEO.1', 'OUT.HDMI.1.VIDEO.1'])

    def test_abbreviated_ids_and_nonmatching_feedback(self):
        self.assertEqual(str(protocol.parse_signal_id('out.sdi.5')), 'OUT.SDI.5.VIDEO.1')
        self.assertIsNone(protocol.parse_signal_id('IN.HDMI.0.VIDEO.1'))
        self.assertIsNone(protocol.parse_signal_id('OUT.HDMI.1.VIDEO.0'))
        self.assertIsNone(protocol.parse_signal_id('OUT.HDMI.1,JUNK'))
        pair = protocol.parse_x_route(protocol.parse_message('~01@X-ROUTE OUT.SDI.5,IN.SDI.1'))
        self.assertEqual(str(pair[0]), 'OUT.SDI.5.VIDEO.1')
        self.assertEqual(str(pair[1]), 'IN.SDI.1.VIDEO.1')
        self.assertIsNone(protocol.parse_x_route(protocol.parse_message(
            '~01@X-ROUTE OUT.HDMI.1.AUDIO.1,IN.HDMI.2.AUDIO.1')))
        self.assertIsNone(protocol.parse_x_route(protocol.parse_message(
            '~01@X-ROUTE IN.HDMI.1.VIDEO.1,OUT.HDMI.2.VIDEO.1')))

    def test_empty_and_duplicate_signal_ids(self):
        self.assertEqual(protocol.parse_signals_list(protocol.parse_message('~01@SIGNALS-LIST []')), [])
        self.assertEqual(len(protocol.parse_signals_list(protocol.parse_message(
            '~01@SIGNALS-LIST [IN.HDMI.1.VIDEO.1,IN.HDMI.1.VIDEO.1]'))), 1)
        self.assertEqual(protocol.parse_signals_list(protocol.parse_message('~01@MODEL VP-778')), [])


class FakeMatrix:
    def __init__(self):
        self.routes = {'OUT.HDBT.4.VIDEO.1': 'IN.HDMI.2.VIDEO.1',
                       'OUT.HDMI.1.VIDEO.1': 'IN.HDMI.1.VIDEO.1'}
        self.commands = []

    async def handle(self, reader, writer):
        try:
            while data := await reader.readuntil(b'\r'):
                cmd = data.decode('ascii').strip()
                self.commands.append(cmd)
                if cmd == '#SIGNALS-LIST?':
                    response = ('~01@SIGNALS-LIST [IN.HDMI.1.VIDEO.1,IN.HDMI.2.VIDEO.1,'
                                'OUT.HDBT.4.VIDEO.1,OUT.HDMI.1.VIDEO.1,'
                                'IN.HDMI.1.AUDIO.1]\r\n')
                elif cmd.startswith('#X-ROUTE? '):
                    output = cmd.split(' ', 1)[1]
                    response = f'~01@X-ROUTE {output},{self.routes[output]}\r\n'
                elif cmd.startswith('#X-ROUTE '):
                    output, source = cmd.split(' ', 1)[1].split(',')
                    self.routes[output] = source
                    response = f'~01@X-ROUTE {output},{source}\r\n'
                else:
                    response = '~01@X-ROUTE ERR003\r\n'
                writer.write(response.encode('ascii'))
                await writer.drain()
        except (asyncio.IncompleteReadError, KeyError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()


class ExtendedClientTest(unittest.IsolatedAsyncioTestCase):
    async def test_discovery_query_and_set(self):
        matrix = FakeMatrix()
        server = await asyncio.start_server(matrix.handle, '127.0.0.1', 0)
        port = server.sockets[0].getsockname()[1]
        messages = []
        client = protocol.KramerClient('127.0.0.1', port, on_message=messages.append)
        try:
            signals = protocol.parse_signals_list(await client.command('SIGNALS-LIST?'))
            self.assertEqual(len(signals), 5)
            query = 'X-ROUTE? OUT.HDBT.4.VIDEO.1'
            first = await client.command(query, matcher=lambda msg: (
                (pair := protocol.parse_x_route(msg)) is not None and
                str(pair[0]) == 'OUT.HDBT.4.VIDEO.1'))
            self.assertEqual(str(protocol.parse_x_route(first)[1]), 'IN.HDMI.2.VIDEO.1')
            setcmd = 'X-ROUTE OUT.HDBT.4.VIDEO.1,IN.HDMI.1.VIDEO.1'
            changed = await client.command(setcmd)
            self.assertEqual(str(protocol.parse_x_route(changed)[1]), 'IN.HDMI.1.VIDEO.1')
            self.assertEqual(str(protocol.parse_x_route(await client.command(query))[1]),
                             'IN.HDMI.1.VIDEO.1')
            self.assertEqual(matrix.commands, ['#SIGNALS-LIST?', '#'+query, '#'+setcmd, '#'+query])
            self.assertEqual(len(messages), 4)
        finally:
            await client.close()
            server.close()
            await server.wait_closed()


if __name__ == '__main__':
    unittest.main()
