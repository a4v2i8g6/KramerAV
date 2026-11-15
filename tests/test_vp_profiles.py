"""VP routing profile integration tests using simulated TCP devices, no HA needed."""

import asyncio
import unittest
from types import SimpleNamespace

from test_coordinator_extended import coord_module, select_module, constants
from importlib import import_module

profiles_module = import_module('kramer_extended_coordinator_test.profiles')
protocol_module = import_module('kramer_extended_coordinator_test.protocol')


class FakeVPDevice:
    """Expose one realistic ROUTE layer/ID set per known VP model."""

    def __init__(self, profile):
        self.profile = profile
        self.routes = {output: profile.input_ids[0] for output in profile.output_ids}
        self.writes = []
        self.unsupported = False

    async def handle(self, reader, writer):
        try:
            while packet := await reader.readuntil(b'\r'):
                command = packet.decode().strip()
                self.writes.append(command)
                if command == '#MODEL?':
                    reply = f'~01@MODEL {self.profile.model}'
                elif command == '#PROT-VER?':
                    reply = '~01@PROT-VER 3000:3.0'
                elif command == '#VERSION?':
                    reply = '~01@VERSION 1.0'
                elif command == '#SIGNALS-LIST?':
                    reply = '~01@SIGNALS-LIST ERR003'
                elif command.startswith('#ROUTE? '):
                    layer, destination = map(int, command.split(' ', 1)[1].split(','))
                    if (self.unsupported or layer != self.profile.route_layer
                            or destination not in self.routes):
                        reply = '~01@ROUTE ERR003'
                    else:
                        reply = f'~01@ROUTE {layer},{destination},{self.routes[destination]} OK'
                elif command.startswith('#ROUTE '):
                    layer, destination, source = map(int, command.split(' ', 1)[1].split(','))
                    if (layer != self.profile.route_layer
                            or destination not in self.routes
                            or source not in self.profile.input_ids):
                        reply = '~01@ROUTE ERR003'
                    else:
                        self.routes[destination] = source
                        reply = f'~01@ROUTE {layer},{destination},{source} OK'
                else:
                    reply = '~01@VID ERR003'
                writer.write((reply + '\r\n').encode())
                await writer.drain()
        except asyncio.IncompleteReadError:
            pass
        finally:
            writer.close()
            await writer.wait_closed()


class ProfileUnitTests(unittest.TestCase):
    def test_exact_model_matching(self):
        get = profiles_module.profile_for_model
        self.assertEqual(get(' vp-440 ').model, 'VP-440')
        self.assertEqual(get('Vp-440X').model, 'VP-440X')
        self.assertIsNone(get('VP-440-unknown'))
        self.assertIsNone(get('VP-772'))
        self.assertIsNone(get('VP-558X'))

    def test_profile_ranges_and_labels(self):
        vp440 = profiles_module.PROFILES['VP-440']
        self.assertEqual((vp440.route_layer, vp440.input_ids, vp440.output_ids),
                         (12, (0, 1, 2, 3, 4, 5), (1,)))
        vp778 = profiles_module.PROFILES['VP-778']
        self.assertEqual((vp778.route_layer, vp778.input_ids, vp778.output_ids),
                         (1, tuple(range(8)), (0, 1)))
        self.assertEqual(len(profiles_module.PROFILES['VP-558'].input_labels), 11)

    def test_parse_route_layer_and_ok_ack(self):
        parse = protocol_module.parse_route
        msg = protocol_module.parse_message('~01@ROUTE 12,1,0 OK')
        self.assertEqual(parse(msg, 'route', layer=12), {1: 0})
        self.assertEqual(parse(msg, 'route', layer=1), {})
        self.assertEqual(parse(protocol_module.parse_message('~01@ROUTE 1,0,7 OK'),
                               'route'), {0: 7})
        self.assertEqual(parse(protocol_module.parse_message('~01@ROUTE ERR003'),
                               'route', layer=12), {})

    def test_profile_labels_and_custom_overrides(self):
        defaults = profiles_module.PROFILES['VP-778'].input_labels
        names = select_module._friendly_names('Computer,,Camera', 8, 'Input', defaults)
        self.assertEqual(names[:4], ['Input 1 — Computer', 'Input 2 — HDMI 2',
                                    'Input 3 — Camera', 'Input 4 — HDMI 4'])


class VPIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def start(self, model, *, counts=(0, 0), family='auto', mode='auto', unsupported=False):
        self.fake = FakeVPDevice(profiles_module.PROFILES[model])
        self.fake.unsupported = unsupported
        self.server = await asyncio.start_server(self.fake.handle, '127.0.0.1', 0)
        port = self.server.sockets[0].getsockname()[1]
        entry = SimpleNamespace(
            data={'host': '127.0.0.1', 'port': port, 'inputs': counts[0],
                  'outputs': counts[1], 'command_family': family,
                  'profile_mode': mode, 'transport': 'tcp'},
            options={}, entry_id='vp-integration-test', title=f'Kramer {model}',
        )
        self.coordinator = coord_module.KramerCoordinator(None, entry)
        return self.coordinator

    async def asyncTearDown(self):
        if hasattr(self, 'coordinator'):
            await self.coordinator.async_close()
        if hasattr(self, 'server'):
            self.server.close()
            await self.server.wait_closed()

    async def test_vp440_zero_based_source_and_layer12(self):
        c = await self.start('VP-440')
        await c.async_initialize()
        self.assertEqual((c.inputs, c.outputs, c.family), (6, 1, 'route'))
        self.assertEqual(c.profile.route_layer, 12)
        await c.async_request_refresh()
        self.assertEqual(c.data, {1: 1})  # Physical HDMI1 source 0 maps to logical 1.
        await c.async_set_route(1, 2)  # Logical input 2 = physical source 1.
        self.assertIn('#ROUTE 12,1,1', self.fake.writes)
        self.assertEqual(c.data, {1: 2})
        self.assertNotIn('#ROUTE 1,1,2', self.fake.writes)

    async def test_vp440x_one_based(self):
        c = await self.start('VP-440X')
        await c.async_initialize()
        await c.async_set_route(1, 5)
        self.assertIn('#ROUTE 1,1,5', self.fake.writes)
        self.assertEqual(c.data, {1: 5})

    async def test_vp558_all_four_outputs(self):
        c = await self.start('VP-558')
        await c.async_initialize()
        await c.async_request_refresh()
        self.assertEqual((c.inputs, c.outputs), (11, 4))
        await c.async_set_route(4, 11)
        self.assertIn('#ROUTE 1,4,11', self.fake.writes)
        self.assertEqual(c.data[4], 11)

    async def test_vp778_independent_scaler_channels(self):
        c = await self.start('VP-778')
        await c.async_initialize()
        await c.async_request_refresh()
        self.assertEqual(c.data, {1: 1, 2: 1})
        self.assertEqual(c.outputs, 2)  # Not four physical output connectors.
        source_labels = select_module._friendly_names('', 8, 'Input', c.profile.input_labels)
        entity = select_module.KramerOutputSelect(c, 2, source_labels, 'Output 2 — Channel 2')
        self.assertEqual(entity.current_option, 'Input 1 — HDMI 1')
        self.assertEqual(entity.extra_state_attributes['physical_output_id'], 1)
        await entity.async_select_option('Input 8 — HDBaseT 2')
        self.assertEqual(entity.extra_state_attributes['physical_input_id'], 7)
        self.assertIn('#ROUTE 1,1,7', self.fake.writes)
        self.assertEqual(c.data, {1: 1, 2: 8})
        # Status notification on physical dest 0, source 2 updates channel 1.
        c._handle_message(protocol_module.parse_message('~01@ROUTE 1,0,2 OK'))
        self.assertEqual(c.data, {1: 3, 2: 8})
        self.assertEqual(c._query('route', 1), 'ROUTE? 1,0')

    async def test_profile_rejects_conflicting_manual_layout(self):
        c = await self.start('VP-778', counts=(8, 4))
        with self.assertRaisesRegex(protocol_module.KramerConnectionError, 'expects 8 inputs and 2'):
            await c.async_initialize()
        self.assertFalse(any(command.startswith('#ROUTE ') for command in self.fake.writes))

    async def test_unverified_profile_not_enabled(self):
        c = await self.start('VP-440', unsupported=True)
        with self.assertRaisesRegex(protocol_module.KramerConnectionError, 'was not confirmed'):
            await c.async_initialize()
        self.assertIsNone(c.profile)
        self.assertFalse(any(command.startswith('#ROUTE ') for command in self.fake.writes))

    async def test_generic_mode_override(self):
        c = await self.start('VP-558', counts=(11, 4), family='route', mode='generic')
        await c.async_initialize()
        self.assertIsNone(c.profile)
        self.assertEqual(c._query('route', 1), 'ROUTE? 1,1')


if __name__ == '__main__':
    unittest.main()
