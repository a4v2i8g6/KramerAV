"""Ensure exported diagnostics never leak local endpoint configuration."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest

from test_coordinator_extended import PKG

ROOT = Path(__file__).resolve().parents[1] / 'custom_components' / 'kramer_av_routing'


def load_diagnostics():
    names = ('homeassistant', 'homeassistant.core', 'homeassistant.config_entries')
    old = {k: sys.modules.get(k) for k in names}
    try:
        for name in names:
            sys.modules[name] = types.ModuleType(name)
        sys.modules['homeassistant.core'].HomeAssistant = type('HomeAssistant', (), {})
        sys.modules['homeassistant.config_entries'].ConfigEntry = type('ConfigEntry', (), {})
        name = f'{PKG}.diagnostics'
        spec = importlib.util.spec_from_file_location(name, ROOT / 'diagnostics.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        for name, value in old.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


diag = load_diagnostics()


class DiagnosticsTest(unittest.TestCase):
    def test_snapshot_does_not_include_address_or_secret(self):
        entry = types.SimpleNamespace(data={
            'host': '10.24.14.30', 'port': 50000, 'protocol': '3000',
            'transport': 'udp', 'password': 'hidden',
        })
        coordinator = types.SimpleNamespace(
            model='VP-444', firmware_version='1.0', protocol_version='3000',
            family='route', profile=None, inputs=12, outputs=1,
            audio_inputs=0, audio_outputs=0, last_update_success=True,
            last_success='2026-11-16T00:00:00+00:00', last_error=None,
            capabilities={}, saved_presets=(), data={1: 5}, audio_routes={},
            client=types.SimpleNamespace(connected=True),
        )
        import json
        output = json.dumps(diag.diagnostics_snapshot(entry, coordinator))
        self.assertNotIn('10.24.14.30', output)
        self.assertNotIn('hidden', output)
        self.assertNotIn('password', output)
        self.assertIn('VP-444', output)
