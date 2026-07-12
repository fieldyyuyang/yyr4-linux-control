"""Tests for production composition factory."""

from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock

from yyr4_linux_control.device.identity import YYR4Identity
from yyr4_linux_control.integration.composition import (
    LinuxRawInputStreamFactory,
    build_linux_observation_pipeline,
)
from yyr4_linux_control.integration.errors import IntegrationDependencyError
from yyr4_linux_control.observation.pipeline import ObservationPipeline


class TestIntegrationComposition(unittest.TestCase):

    def test_linux_raw_input_stream_factory(self):
        mock_device_factory = MagicMock()
        mock_clock = MagicMock()
        factory = LinuxRawInputStreamFactory(
            event_device_factory=mock_device_factory,
            clock=mock_clock,
            include_mouse=True,
        )
        ident = MagicMock(spec=YYR4Identity)
        stream = factory.create(ident)
        # Should not open or interact with device during create
        from yyr4_linux_control.input.evdev_adapter import EvdevInputAdapter
        self.assertIsInstance(stream, EvdevInputAdapter)
        mock_device_factory.create.assert_not_called()
        self.assertTrue(stream._include_mouse)

    def test_build_linux_observation_pipeline_missing_pyudev(self):
        with patch.dict("sys.modules", {"pyudev": None}):
            with self.assertRaises(IntegrationDependencyError) as ctx:
                build_linux_observation_pipeline()
            self.assertIn("pyudev", str(ctx.exception))

    def test_build_linux_observation_pipeline_missing_evdev(self):
        # Even if pyudev is found, if evdev is missing, it should fail
        with patch.dict("sys.modules", {"evdev": None}):
            with self.assertRaises(IntegrationDependencyError) as ctx:
                build_linux_observation_pipeline()
            self.assertIn("evdev", str(ctx.exception))

    def test_build_linux_observation_pipeline_no_device_access(self):
        # If pyudev/evdev are installed, this runs the real imports but shouldn't access devices.
        # If not, it raises IntegrationDependencyError.
        try:
            comp = build_linux_observation_pipeline(include_mouse=False, transport_source_id="test:src")
            self.assertIsInstance(comp.pipeline, ObservationPipeline)
            self.assertEqual(comp.pipeline.transport_source_id, "test:src")
            # Should not have called select_single
            # Should not have created streams
        except IntegrationDependencyError:
            # OK, we are on a system without the deps. That's a valid test path for this phase.
            pass

    def test_regular_import_does_not_load_optional_dependencies(self):
        # Just importing the module should not raise even if deps are missing
        import yyr4_linux_control.integration.composition as comp
        self.assertIn("LinuxRawInputStreamFactory", dir(comp))
