"""Coordinator and entity tests using lightweight HA stubs and a fake TCP matrix."""

import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'custom_components' / 'kramer_av_routing'
PKG = 'kramer_extended_coordinator_test'


class CoordinatorStub:
    @classmethod
    def __class_getitem__(cls, _item):
        return cls

    def __init__(self, hass, logger, name, update_interval):
        self.data = None
        self.last_update_success = True

    def async_set_updated_data(self, data):
        self.data = data

    def async_update_listeners(self):
        pass

    async def async_request_refresh(self):
        self.data = await self._async_update_data()


class CoordinatorEntityStub:
    @classmethod
    def __class_getitem__(cls, _item):
        return cls

    def __init__(self, coordinator):
        self.coordinator = coordinator

    @property
    def available(self):
        return True


class SelectEntityStub:
    pass


class HomeAssistantErrorStub(Exception):
    pass


def _load_local_source():
    # A small HA stub permits running coordinator tests in ordinary Python.
    # Restore public module names immediately after imports to avoid affecting
    # unrelated test modules or a real Home Assistant installation.
    stubs = {
        'homeassistant': types.ModuleType('homeassistant'),
        'homeassistant.core': types.ModuleType('homeassistant.core'),
        'homeassistant.const': types.ModuleType('homeassistant.const'),
        'homeassistant.components': types.ModuleType('homeassistant.components'),
        'homeassistant.components.select': types.ModuleType('homeassistant.components.select'),
        'homeassistant.components.switch': types.ModuleType('homeassistant.components.switch'),
        'homeassistant.components.number': types.ModuleType('homeassistant.components.number'),
        'homeassistant.helpers.entity': types.ModuleType('homeassistant.helpers.entity'),
        'homeassistant.exceptions': types.ModuleType('homeassistant.exceptions'),
        'homeassistant.helpers': types.ModuleType('homeassistant.helpers'),
        'homeassistant.helpers.device_registry': types.ModuleType('homeassistant.helpers.device_registry'),
        'homeassistant.helpers.update_coordinator': types.ModuleType('homeassistant.helpers.update_coordinator'),
    }
    stubs['homeassistant.core'].HomeAssistant = type('HomeAssistant', (), {})
    stubs['homeassistant.const'].Platform = types.SimpleNamespace(SELECT='select', SWITCH='switch', NUMBER='number')
    stubs['homeassistant.components.select'].SelectEntity = SelectEntityStub
    stubs['homeassistant.components.switch'].SwitchEntity = type('SwitchEntity', (), {})
    stubs['homeassistant.components.number'].NumberEntity = type('NumberEntity', (), {})
    stubs['homeassistant.helpers.entity'].EntityCategory = types.SimpleNamespace(CONFIG='config')
    stubs['homeassistant.exceptions'].HomeAssistantError = HomeAssistantErrorStub
    stubs['homeassistant.helpers.device_registry'].DeviceInfo = dict
    stubs['homeassistant.helpers.update_coordinator'].DataUpdateCoordinator = CoordinatorStub
    stubs['homeassistant.helpers.update_coordinator'].UpdateFailed = type('UpdateFailed', (Exception,), {})
    stubs['homeassistant.helpers.update_coordinator'].CoordinatorEntity = CoordinatorEntityStub
    old = {key: sys.modules.get(key) for key in stubs}
    pkg = types.ModuleType(PKG)
    pkg.__path__ = [str(ROOT)]
    sys.modules[PKG] = pkg
    sys.modules.update(stubs)
    try:
        for mod in ('const', 'protocol', 'profiles', 'capabilities', 'coordinator', 'control_entity', 'select', 'switch', 'number'):
            module_name = f'{PKG}.{mod}'
            spec = importlib.util.spec_from_file_location(module_name, ROOT / f'{mod}.py')
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
    finally:
        for key, value in old.items():
            if value is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value
    return (sys.modules[f'{PKG}.coordinator'],
            sys.modules[f'{PKG}.select'], sys.modules[f'{PKG}.const'])


coord_module, select_module, constants = _load_local_source()


class MatrixStub:
    def __init__(self, extended=True):
        self.extended = extended
        self.writes = []
        self.map = {'OUT.HDBT.4.VIDEO.1': 'IN.HDMI.2.VIDEO.1',
                    'OUT.HDMI.1.VIDEO.1': 'IN.HDMI.1.VIDEO.1'}

    async def handle(self, reader, writer):
        try:
            while packet := await reader.readuntil(b'\r'):
                cmd = packet.decode().strip()
                self.writes.append(cmd)
                if cmd == '#MODEL?':
                    reply = '~01@MODEL VP-TEST\r\n'
                elif cmd == '#PROT-VER?':
                    reply = '~01@PROT-VER 3000:3.0\r\n'
                elif cmd == '#VERSION?':
                    reply = '~01@VERSION 1.2.3\r\n'
                elif cmd == '#SIGNALS-LIST?':
                    reply = ('~01@SIGNALS-LIST [IN.HDMI.1.VIDEO.1,IN.HDMI.2.VIDEO.1,'
                             'OUT.HDBT.4.VIDEO.1,OUT.HDMI.1.VIDEO.1,'
                             'IN.HDMI.1.AUDIO.1]\r\n') if self.extended else '~01@SIGNALS-LIST ERR003\r\n'
                elif cmd.startswith('#X-ROUTE? '):
                    out = cmd.split(' ', 1)[1]
                    reply = f'~01@X-ROUTE {out},{self.map[out]}\r\n'
                elif cmd.startswith('#X-ROUTE '):
                    out, source = cmd.split(' ', 1)[1].split(',')
                    self.map[out] = source
                    reply = f'~01@X-ROUTE {out},{source}\r\n'
                elif cmd == '#ROUTE? 1,1':
                    reply = '~01@ROUTE 1,1,2\r\n'
                elif cmd == '#ROUTE 1,1,1':
                    reply = '~01@ROUTE 1,1,1\r\n'
                else:
                    reply = f'~01@{cmd.lstrip("#").split()[0].rstrip("?")} ERR003\r\n'
                writer.write(reply.encode())
                await writer.drain()
        except (asyncio.IncompleteReadError, KeyError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()


class CoordinatorIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def _make(self, extended=True, family='auto'):
        self.fake = MatrixStub(extended=extended)
        self.server = await asyncio.start_server(self.fake.handle, '127.0.0.1', 0)
        port = self.server.sockets[0].getsockname()[1]
        entry = types.SimpleNamespace(
            data={'host': '127.0.0.1', 'port': port, 'inputs': 0 if extended else 2,
                  'outputs': 0 if extended else 1, 'command_family': family,
                  'transport': 'tcp'},
            options={}, entry_id='example', title='Kramer VP-TEST')
        self.coordinator = coord_module.KramerCoordinator(None, entry)
        return self.coordinator

    async def asyncTearDown(self):
        if hasattr(self, 'coordinator'):
            await self.coordinator.async_close()
        if hasattr(self, 'server'):
            self.server.close()
            await self.server.wait_closed()

    async def test_extended_discovery_entity_names_and_route(self):
        coordinator = await self._make()
        await coordinator.async_initialize()
        self.assertEqual(coordinator.family, 'x_route')
        self.assertEqual((coordinator.inputs, coordinator.outputs), (2, 2))
        await coordinator.async_request_refresh()
        self.assertEqual(coordinator.data, {1: 2, 2: 1})
        source_options = select_module._friendly_names('', 2, 'Input')
        source_options = [f'{n} ({s.port_type} {s.port_number})'
                          for n, s in zip(source_options, coordinator.x_inputs)]
        entity = select_module.KramerOutputSelect(coordinator, 1, source_options, 'HDBT 4')
        self.assertIn('out_hdbt_4_video_1', entity._attr_unique_id)
        self.assertEqual(entity.current_option, 'Input 2 (HDMI 2)')
        await entity.async_select_option('Input 1 (HDMI 1)')
        self.assertEqual(coordinator.data, {1: 1, 2: 1})
        self.assertIn('#X-ROUTE OUT.HDBT.4.VIDEO.1,IN.HDMI.1.VIDEO.1', self.fake.writes)
        self.assertNotIn('#ROUTE 1,1,1', self.fake.writes)

    async def test_legacy_auto_fallback(self):
        coordinator = await self._make(extended=False)
        await coordinator.async_initialize()
        self.assertEqual(coordinator.family, 'route')
        self.assertEqual((coordinator.inputs, coordinator.outputs), (2, 1))
        await coordinator.async_request_refresh()
        self.assertEqual(coordinator.data, {1: 2})
        await coordinator.async_set_route(1, 1)
        self.assertIn('#ROUTE 1,1,1', self.fake.writes)


if __name__ == '__main__':
    unittest.main()
