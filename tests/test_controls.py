"""Read-only capability discovery and control feedback tests, no HA/hardware needed."""

import asyncio
from importlib import import_module
from types import SimpleNamespace
import unittest

from test_coordinator_extended import coord_module

package = 'kramer_extended_coordinator_test'
capabilities = import_module(f'{package}.capabilities')
protocol = import_module(f'{package}.protocol')
switches = import_module(f'{package}.switch')
numbers = import_module(f'{package}.number')
selects = import_module(f'{package}.select')


class ControlSpecTests(unittest.TestCase):
    def test_query_and_write_generation(self):
        spec = capabilities.ControlSpec('audio', 'Volume', 'number', 'AUD-LVL', (1, 0), 0, 100)
        self.assertEqual(spec.get_command(), 'AUD-LVL? 1,0')
        self.assertEqual(spec.set_command(85), 'AUD-LVL 1,0,85')
        with self.assertRaises(ValueError):
            spec.set_command(101)
        with self.assertRaises(ValueError):
            spec.set_command(-1)
        with self.assertRaises(ValueError):
            spec.set_command(True)

    def test_strict_response_matching(self):
        spec = capabilities.ControlSpec('mute', 'Mute', 'switch', 'MUTE', (1,))
        self.assertEqual(spec.decode(protocol.parse_message('~01@MUTE 1,0')), 0)
        self.assertEqual(spec.decode(protocol.parse_message('~01@MUTE 1,1 OK')), 1)
        self.assertEqual(spec.decode(protocol.parse_message('~01@MUTE 1,1.')), 1)
        self.assertIsNone(spec.decode(protocol.parse_message('~01@MUTE 2,1')))
        self.assertIsNone(spec.decode(protocol.parse_message('~01@MUTE ERR003')))
        self.assertIsNone(spec.decode(protocol.parse_message('~01@MUTE 1,2')))
        self.assertIsNone(spec.decode(protocol.parse_message('~01@MUTE 1,1,0')))

    def test_resolution_options_use_documented_vp444_codes(self):
        spec = next(s for s in capabilities.candidate_controls('VP-444', 1)
                    if s.key == 'output_resolution')
        self.assertEqual(spec.option_code('1080p 60Hz'), 217)
        self.assertEqual(spec.option_label(222), 'Native output 1')
        self.assertIsNone(spec.decode(protocol.parse_message('~01@VID-RES 1,1,0,199')))
        self.assertEqual(spec.decode(protocol.parse_message('~01@VID-RES 1,1,0,217')), 217)

    def test_vp444_unit_scale_and_generic_no_guessed_volume(self):
        v = capabilities.candidate_controls('VP-444', 1)
        self.assertEqual(next(s for s in v if s.key == 'output_volume').maximum, 100)
        generic = capabilities.candidate_controls('VS-88H2A', 8)
        self.assertFalse(any(s.command == 'AUD-LVL' for s in generic))
        self.assertIn('audio_mute_8', [s.key for s in generic])
        self.assertNotIn('audio_mute_17', [s.key for s in generic])


class FakeVP444(asyncio.DatagramProtocol):
    def __init__(self):
        self.requests = []
        self.current = {'LOCK-FP': 0, 'STANDBY': 0, 'MUTE': 0, 'VMUTE': 1,
                        'VFRZ': 0, 'AUD-LVL': 50, 'SCLR-AS': 0,
                        'SCLR-AUDIO-DELAY': 0, 'VID-RES': 217}
        self.prefixes = {
            'LOCK-FP': '', 'STANDBY': '', 'MUTE': '1', 'VMUTE': '1',
            'VFRZ': '1', 'AUD-LVL': '1,0', 'SCLR-AS': '1',
            'SCLR-AUDIO-DELAY': '1', 'VID-RES': '1,1,0',
        }

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, address):
        cmd = data.decode('ascii').strip()
        self.requests.append(cmd)
        if cmd == '#MODEL?':
            response = '~01@MODEL VP-444'
        elif cmd == '#PROT-VER?':
            response = '~01@PROT-VER 3000:3.0'
        elif cmd == '#VERSION?':
            response = '~01@VERSION 1.40'
        elif cmd == '#SIGNALS-LIST?':
            response = '~01@SIGNALS-LIST ERR003'
        elif cmd == '#ROUTE? 12,1':
            response = '~01@ROUTE 12,1,0'
        elif cmd.startswith('#ROUTE 12,1,'):
            response = f'~01@ROUTE 12,1,{cmd.rsplit(",", 1)[1]}'
        else:
            body = cmd.lstrip('#')
            command, _, params = body.partition(' ')
            key = command.rstrip('?')
            if key in self.current:
                pref = self.prefixes[key]
                if command.endswith('?') and params == pref:
                    val = self.current[key]
                    response = f'~01@{key} {pref + "," if pref else ""}{val}'
                elif not command.endswith('?') and params.startswith(pref + ',' if pref else ''):
                    proposed = params.rsplit(',', 1)[-1]
                    self.current[key] = int(proposed)
                    response = f'~01@{key} {pref + "," if pref else ""}{proposed} OK'
                else:
                    response = f'~01@{key} ERR003'
            else:
                response = f'~01@{key} ERR003'
        self.transport.sendto((response + '\r\n').encode(), address)


class DeviceDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        loop = asyncio.get_running_loop()
        self.device = FakeVP444()
        self.server, _ = await loop.create_datagram_endpoint(
            lambda: self.device, local_addr=('127.0.0.1', 0)
        )
        port = self.server.get_extra_info('sockname')[1]
        entry = SimpleNamespace(
            data={'host': '127.0.0.1', 'port': port, 'inputs': 0, 'outputs': 0,
                  'command_family': 'auto', 'profile_mode': 'auto', 'transport': 'udp'},
            options={}, entry_id='vp444-controls', title='VP-444 test',
        )
        self.coordinator = coord_module.KramerCoordinator(None, entry)

    async def asyncTearDown(self):
        await self.coordinator.async_close()
        self.server.close()

    async def test_discovery_is_read_only(self):
        c = self.coordinator
        await c.async_initialize()
        self.assertEqual(c.model, 'VP-444')
        self.assertEqual(len(c.capabilities), 9)
        self.assertEqual(c.control_values['output_volume'], 50)
        self.assertEqual(c.control_values['video_enabled_1'], 1)
        self.assertFalse(any('#MUTE ' in command or '#VMUTE ' in command or
                             '#LOCK-FP ' in command for command in self.device.requests))
        self.assertTrue(all(cmd.startswith('#') for cmd in self.device.requests))

    async def test_validated_writes_and_external_feedback(self):
        c = self.coordinator
        await c.async_initialize()
        await c.async_request_refresh()
        await c.async_set_control('audio_mute_1', 1)
        self.assertIn('#MUTE 1,1', self.device.requests)
        self.assertEqual(c.control_values['audio_mute_1'], 1)
        await c.async_set_control('output_volume', 83)
        self.assertIn('#AUD-LVL 1,0,83', self.device.requests)
        await c.async_set_control('output_resolution', 222)
        self.assertIn('#VID-RES 1,1,0,222', self.device.requests)
        with self.assertRaises(ValueError):
            await c.async_set_control('output_volume', -1)
        with self.assertRaises(ValueError):
            await c.async_set_control('output_volume', 101)
        c._handle_message(protocol.parse_message('~01@MUTE 1,0'))
        self.assertEqual(c.control_values['audio_mute_1'], 0)
        c._handle_message(protocol.parse_message('~01@MUTE 2,1'))
        self.assertEqual(c.control_values['audio_mute_1'], 0)
        self.assertNotIn('#AUD-LVL 1,0,101', self.device.requests)

    async def test_ha_entities_control_expected_commands(self):
        c = self.coordinator
        await c.async_initialize()
        mute = switches.KramerControlSwitch(c, c.capabilities['audio_mute_1'])
        self.assertFalse(mute.is_on)
        await mute.async_turn_on()
        self.assertTrue(mute.is_on)
        volume = numbers.KramerControlNumber(c, c.capabilities['output_volume'])
        self.assertEqual(volume.native_value, 50.0)
        await volume.async_set_native_value(67)
        self.assertEqual(volume.native_value, 67.0)
        scaler = selects.KramerControlSelect(c, c.capabilities['auto_sync_off'])
        self.assertEqual(scaler.current_option, 'Disabled')
        await scaler.async_select_option('Fast')
        self.assertEqual(scaler.current_option, 'Fast')
        self.assertIn('#SCLR-AS 1,1', self.device.requests)


if __name__ == '__main__':
    unittest.main()


class FakeGenericMatrix:
    """Typical VS-like matrix with only a subset of common controls."""

    def __init__(self):
        self.commands = []
        self.mute = {1: 0, 2: 1}

    async def handle(self, reader, writer):
        try:
            while raw := await reader.readuntil(b'\r'):
                command = raw.decode().strip()
                self.commands.append(command)
                if command == '#MODEL?':
                    answer = '~01@MODEL VS-TEST'
                elif command == '#PROT-VER?':
                    answer = '~01@PROT-VER 3000:3.0'
                elif command == '#VERSION?':
                    answer = '~01@VERSION 1.0'
                elif command == '#INFO-IO?':
                    answer = '~01@INFO-IO IN 4,OUT 2'
                elif command == '#LOCK-FP?':
                    answer = '~01@LOCK-FP 0 OK'
                elif command in ('#MUTE? 1', '#MUTE? 2'):
                    out = int(command[-1]); answer = f'~01@MUTE {out},{self.mute[out]}'
                elif command.startswith('#MUTE '):
                    out, val = map(int, command.split(' ', 1)[1].split(','))
                    self.mute[out] = val
                    answer = f'~01@MUTE {out},{val}'
                elif command.startswith('#ROUTE? 1,'):
                    out = int(command[-1]); answer = f'~01@ROUTE 1,{out},1'
                else:
                    # Different firmware families use either error format.
                    answer = '~01@ERR 002' if command == '#STANDBY?' else (
                        f'~01@{command.lstrip("#").split()[0].rstrip("?")} ERR003'
                    )
                writer.write((answer + '\r\n').encode())
                await writer.drain()
        except asyncio.IncompleteReadError:
            pass
        finally:
            writer.close()
            await writer.wait_closed()


class GenericCapabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_supported_commands_only_and_multiple_outputs(self):
        fake = FakeGenericMatrix()
        server = await asyncio.start_server(fake.handle, '127.0.0.1', 0)
        entry = SimpleNamespace(
            data={'host': '127.0.0.1', 'port': server.sockets[0].getsockname()[1],
                  'inputs': 0, 'outputs': 0, 'command_family': 'route', 'transport': 'tcp'},
            options={}, entry_id='generic-controls', title='VS-TEST',
        )
        coordinator = coord_module.KramerCoordinator(None, entry)
        try:
            await coordinator.async_initialize()
            self.assertEqual(set(coordinator.capabilities),
                             {'front_panel_lock', 'audio_mute_1', 'audio_mute_2'})
            self.assertNotIn('#MUTE 1,1', fake.commands)
            self.assertNotIn('#VMUTE? 2', fake.commands)  # Probed output 1 first; rejected.
            await coordinator.async_set_control('audio_mute_2', 0)
            self.assertEqual(fake.mute[2], 0)
            self.assertIn('#MUTE 2,0', fake.commands)
        finally:
            await coordinator.async_close()
            server.close()
            await server.wait_closed()
