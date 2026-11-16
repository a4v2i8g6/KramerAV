"""Advanced audio/HDCP and saved-presets tests; no hardware or HA needed."""

import asyncio
from importlib import import_module
from types import SimpleNamespace
import unittest

from test_coordinator_extended import coord_module
from test_controls import FakeVP444

PKG = "kramer_extended_coordinator_test"
capabilities = import_module(f"{PKG}.capabilities")
protocol = import_module(f"{PKG}.protocol")
presets = import_module(f"{PKG}.presets")
buttons = import_module(f"{PKG}.button")
sensors = import_module(f"{PKG}.binary_sensor")


class AdvancedSpecTests(unittest.TestCase):
    def test_vp444_hdcp_address_and_modes(self):
        specs = {s.key: s for s in capabilities.candidate_controls("VP-444", 1)}
        self.assertEqual(specs["hdcp_input_1"].get_command(), "HDCP-MOD? 0,0")
        self.assertEqual(specs["hdcp_input_10"].set_command(1), "HDCP-MOD 0,9,1")
        self.assertEqual(specs["hdcp_output_2"].set_command(3), "HDCP-MOD 1,1,3")
        self.assertFalse(specs["hdcp_input_1"].enabled_default)
        self.assertIsNone(specs["hdcp_input_1"].decode(protocol.parse_message("~01@HDCP-MOD 1,0,1")))
        with self.assertRaises(ValueError):
            specs["hdcp_output_2"].set_command(1)
        self.assertEqual(specs["mic_2_gain"].get_command(), "MIC-GAIN? 0,1")
        self.assertEqual(specs["talkover_param_4"].set_command(200), "MIC-TLK 0,4,200")
        with self.assertRaises(ValueError):
            specs["talkover_param_4"].set_command(201)
        with self.assertRaises(ValueError):
            specs["display_connected_1"].set_command(0)

    def test_no_guessed_hdcp_for_unknown_model(self):
        generic = capabilities.candidate_controls("VS-TEST", 4)
        self.assertFalse(any(s.command in ("HDCP-MOD", "MIC-GAIN", "EQ-LVL") for s in generic))
        vp558 = {s.key: s for s in capabilities.candidate_controls("VP-558", 4)}
        self.assertEqual(vp558["microphone_gain"].get_command(), "MIC-GAIN? 0")
        self.assertEqual(vp558["hdcp_output_4"].get_command(), "HDCP-MOD? 1,4")
        self.assertEqual(vp558["audio_eq_8"].get_command(), "EQ-LVL? 0,8")
        self.assertFalse(vp558["audio_eq_8"].enabled_default)
        self.assertEqual(vp558["audio_eq_8"].maximum, 40)

    def test_preset_parser_rejects_untrusted_lists(self):
        parse = protocol.parse_message
        self.assertEqual(presets.parse_saved_presets(parse("~01@PRST-LST 2,1,2,60")), (2, 1, 60))
        self.assertEqual(presets.parse_saved_presets(parse("~01@PRST-LST")), ())
        self.assertIsNone(presets.parse_saved_presets(parse("~01@PRST-LST 0,1")))
        self.assertIsNone(presets.parse_saved_presets(parse("~01@PRST-LST 1,cat")))
        self.assertIsNone(presets.parse_saved_presets(parse("~01@ROUTE 1,2,3")))
        self.assertEqual(presets.parse_recalled_preset(parse("~01@PRST-RCL 3 OK")), 3)
        self.assertIsNone(presets.parse_recalled_preset(parse("~01@PRST-RCL ERR003")))


class AdvancedVP444(FakeVP444):
    def __init__(self):
        super().__init__()
        self.advanced = {}
        for i in range(10):
            self.advanced[("HDCP-MOD", f"0,{i}")] = 1
        for i in range(2):
            self.advanced[("HDCP-MOD", f"1,{i}")] = 2
            self.advanced[("DISPLAY", str(i))] = int(i == 0)
            self.advanced[("MIC-GAIN", f"0,{i}")] = 35 + i
        self.advanced.update({
            ("MIX", "1"): 3, ("TLK", "1"): 2, ("IMAGE-PROP", "1"): 2,
        })
        for param in range(5):
            self.advanced[("MIC-TLK", f"0,{param}")] = 50

    def datagram_received(self, data, address):
        raw = data.decode('ascii').strip()
        command, _, args = raw.removeprefix("#").partition(" ")
        key = command.rstrip("?")
        if command.endswith("?") and (key, args) in self.advanced:
            self.requests.append(raw)
            value = self.advanced[(key, args)]
            self.transport.sendto((f"~01@{key} {args},{value}\r\n").encode(), address)
            return
        elif not command.endswith("?") and "," in args:
            addr, value = args.rsplit(",", 1)
            if (key, addr) in self.advanced and key != "DISPLAY":
                self.requests.append(raw)
                self.advanced[(key, addr)] = int(value)
                self.transport.sendto((f"~01@{key} {addr},{value} OK\r\n").encode(), address)
                return
        super().datagram_received(data, address)


class AdvancedVP444Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        loop = asyncio.get_running_loop()
        self.device = AdvancedVP444()
        self.server, _ = await loop.create_datagram_endpoint(
            lambda: self.device, local_addr=("127.0.0.1", 0))
        port = self.server.get_extra_info("sockname")[1]
        entry = SimpleNamespace(data={
            'host': '127.0.0.1', 'port': port, 'inputs': 0, 'outputs': 0,
            'command_family': 'auto', 'profile_mode': 'auto', 'transport': 'udp'},
            options={}, entry_id='vp444-advanced', title='VP-444')
        self.c = coord_module.KramerCoordinator(None, entry)

    async def asyncTearDown(self):
        await self.c.async_close()
        self.server.close()

    async def test_discovery_is_read_only_and_feedback_is_address_scoped(self):
        await self.c.async_initialize()
        self.assertIn('hdcp_input_10', self.c.capabilities)
        self.assertIn('hdcp_output_2', self.c.capabilities)
        self.assertIn('display_connected_1', self.c.capabilities)
        self.assertIn('mic_2_gain', self.c.capabilities)
        self.assertIn('talkover_param_4', self.c.capabilities)
        self.assertNotIn('PRST-LST?', ' '.join(self.device.requests))
        self.assertTrue(all(not req.split(' ')[0].startswith('#HDCP-MOD') or '? ' in req
                            for req in self.device.requests))
        self.assertFalse(any('#PRST-RCL ' in req for req in self.device.requests))
        connected = sensors.KramerControlBinarySensor(
            self.c, self.c.capabilities['display_connected_1'])
        self.assertTrue(connected.is_on)
        self.assertIsNone(self.c.capabilities['mic_1_gain'].decode(
            protocol.parse_message('~01@MIC-GAIN 0,1,99')))
        await self.c.async_set_control('mic_1_gain', 60)
        self.assertIn('#MIC-GAIN 0,0,60', self.device.requests)
        await self.c.async_set_control('hdcp_output_2', 3)
        self.assertIn('#HDCP-MOD 1,1,3', self.device.requests)
        self.c._handle_message(protocol.parse_message('~01@HDCP-MOD 0,1,0'))
        self.assertEqual(self.c.control_values['hdcp_input_2'], 0)
        self.assertEqual(self.c.control_values['hdcp_input_1'], 1)


class SimulatedPresetMatrix:
    def __init__(self):
        self.requests = []
        self.source = 1

    async def handle(self, reader, writer):
        try:
            while raw := await reader.readuntil(b'\r'):
                cmd = raw.decode().strip()
                self.requests.append(cmd)
                if cmd == '#MODEL?': response = '~01@MODEL VS-TEST'
                elif cmd == '#VERSION?': response = '~01@VERSION 1.0'
                elif cmd == '#PROT-VER?': response = '~01@PROT-VER 3000:3.0'
                elif cmd == '#INFO-IO?': response = '~01@INFO-IO IN 4,OUT 1'
                elif cmd == '#ROUTE? 1,1': response = f'~01@ROUTE 1,1,{self.source}'
                elif cmd == '#PRST-LST?': response = '~01@PRST-LST 1,3,7'
                elif cmd == '#PRST-RCL 3':
                    self.source = 4
                    response = '~01@PRST-RCL 3 OK'
                else: response = '~01@ERR 002'
                writer.write((response + '\r\n').encode())
                await writer.drain()
        except asyncio.IncompleteReadError:
            pass
        finally:
            writer.close()
            await writer.wait_closed()


class PresetIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.device = SimulatedPresetMatrix()
        self.server = await asyncio.start_server(self.device.handle, "127.0.0.1", 0)
        port = self.server.sockets[0].getsockname()[1]
        entry = SimpleNamespace(data={
            'host': '127.0.0.1', 'port': port, 'inputs': 0, 'outputs': 0,
            'command_family': 'auto', 'transport': 'tcp'},
            options={}, entry_id='preset-try', title='VS-TEST')
        self.c = coord_module.KramerCoordinator(None, entry)

    async def asyncTearDown(self):
        await self.c.async_close()
        self.server.close()
        await self.server.wait_closed()

    async def test_discover_and_recall_saved_only(self):
        await self.c.async_initialize()
        self.assertEqual(self.c.saved_presets, (1,3,7))
        self.assertNotIn('#PRST-RCL 3', self.device.requests)
        await self.c.async_request_refresh()
        self.assertEqual(self.c.data, {1:1})
        with self.assertRaises(ValueError):
            await self.c.async_recall_preset(2)
        button = buttons.KramerPresetRecallButton(self.c, 3)
        self.assertTrue(button.available)
        await button.async_press()
        self.assertEqual(self.c.data, {1:4})
        self.assertIn('#PRST-RCL 3', self.device.requests)
        self.assertNotIn('#PRST-STO 3', self.device.requests)


if __name__ == "__main__":
    unittest.main()
