"""Hardware-free integration tests of the shared 2000 coordinator and HA selectors."""
from __future__ import annotations

import asyncio
import sys
import unittest

from test_coordinator_extended import PKG, select_module, constants
from test_protocol2000 import _FakeMatrix

coordinator_module = sys.modules[f"{PKG}.coordinator2000"]
binary_sensor_module = sys.modules[f"{PKG}.binary_sensor"]


class _Entry:
    entry_id = "test_protocol_2000"
    title = "Kramer Protocol 2000 4x2 (machine 1)"
    options = {}
    data = {
        "host": "127.0.0.1", "port": 0, "transport": "tcp",
        "inputs": 0, "outputs": 0, "command_family": "auto",
        "profile_mode": "auto", "machine_id": 1, "protocol": "2000",
    }


class Coordinator2000Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.dev = _FakeMatrix()
        self.server = await asyncio.start_server(self.dev.handle, "127.0.0.1", 0)
        self.entry = _Entry()
        self.entry.data = {**_Entry.data, "port": self.server.sockets[0].getsockname()[1]}
        self.coordinator = coordinator_module.Kramer2000Coordinator(None, self.entry)
        await self.coordinator.async_initialize()
        self.coordinator.data = await self.coordinator._async_update_data()

    async def asyncTearDown(self):
        await self.coordinator.async_close()
        self.server.close()
        await self.server.wait_closed()

    async def test_discovery_audio_and_video(self):
        c = self.coordinator
        self.assertEqual((c.inputs, c.outputs), (4, 2))
        self.assertEqual((c.audio_inputs, c.audio_outputs), (3, 2))
        self.assertEqual(c.data, {1: 2, 2: 1})
        self.assertEqual(c.audio_routes, {1: 3, 2: 2})
        self.assertIn("front_panel_lock", c.capabilities)

    async def test_independent_routes_and_entity_options(self):
        c = self.coordinator
        ent = select_module.KramerOutputSelect(c, 1, [f"Input {i}" for i in range(1, 5)], "Output 1")
        self.assertEqual(ent.current_option, "Input 2")
        self.assertEqual(ent._attr_options, ["Disconnected", "Input 1", "Input 2", "Input 3", "Input 4"])
        await ent.async_select_option("Input 4")
        self.assertEqual(c.data[1], 4)
        audio = select_module.KramerAudioSelect(c, 2, [f"Input {i}" for i in range(1, 4)])
        self.assertEqual(audio.current_option, "Input 2")
        await audio.async_select_option("Input 1")
        self.assertEqual(c.audio_routes[2], 1)

    async def test_connection_sensor_reports_failed_poll(self):
        sensor = binary_sensor_module.KramerConnectionBinarySensor(self.coordinator)
        self.assertTrue(sensor.is_on)
        self.coordinator.last_update_success = False
        self.assertFalse(sensor.is_on)
        self.assertTrue(sensor.available)

    async def test_verified_frontpanel_lock(self):
        await self.coordinator.async_set_control("front_panel_lock", 1)
        self.assertEqual(self.coordinator.control_values["front_panel_lock"], 1)
        self.assertEqual(self.dev.locked, 1)
