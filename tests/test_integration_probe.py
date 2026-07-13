"""Tests for the integration probe module."""

from __future__ import annotations

import asyncio
import unittest

from yyr4_linux_control.domain.controls import PhysicalControl, ControlKind, ControlPhase
from yyr4_linux_control.domain.events import ControlEvent
from yyr4_linux_control.transport.codebook import TransportCode
from yyr4_linux_control.observation.errors import ObservationInputError
from yyr4_linux_control.integration.errors import IntegrationConfigurationError, IntegrationSafetyError
from yyr4_linux_control.integration.probe import (
    ProbeAuthorization,
    ProbeConfig,
    ProbeEvent,
    ProbeResult,
    ProbeTermination,
    ProbeRunner,
    validate_probe_authorization,
)


class FakePipeline:
    def __init__(self, events_to_yield, sleep_time=0.0):
        self.events_to_yield = events_to_yield
        self.sleep_time = sleep_time
        self.closed = False
        self.error_to_raise = None
        self.cancel_to_raise = False

    def snapshot_diagnostics(self):
        return "fake_diagnostics"

    async def observe(self):
        if self.cancel_to_raise:
            raise asyncio.CancelledError()
        if self.error_to_raise:
            raise self.error_to_raise
        for e in self.events_to_yield:
            if self.sleep_time > 0:
                await asyncio.sleep(self.sleep_time)
            yield e

    async def close(self):
        self.closed = True


class TestProbeAuthorization(unittest.TestCase):

    def test_authorization_all_true(self):
        auth = ProbeAuthorization(True, True, True)
        validate_probe_authorization(auth)  # Should not raise

    def test_authorization_combinations(self):
        # 8 combinations, only (True, True, True) passes
        for a in (True, False):
            for b in (True, False):
                for c in (True, False):
                    auth = ProbeAuthorization(a, b, c)
                    if a and b and c:
                        validate_probe_authorization(auth)
                    else:
                        with self.assertRaises(IntegrationSafetyError) as ctx:
                            validate_probe_authorization(auth)
                        if not a:
                            self.assertIn("read-only", str(ctx.exception))
                        elif not b:
                            self.assertIn("transport profile", str(ctx.exception))
                        elif not c:
                            self.assertIn("no actions", str(ctx.exception))


class TestProbeConfig(unittest.TestCase):

    def test_default_valid(self):
        c = ProbeConfig()
        self.assertEqual(c.max_control_events, 32)
        self.assertEqual(c.timeout_seconds, 30.0)

    def test_invalid_max_events(self):
        with self.assertRaises(IntegrationConfigurationError):
            ProbeConfig(max_control_events=0)
        with self.assertRaises(IntegrationConfigurationError):
            ProbeConfig(max_control_events=257)
        with self.assertRaises(IntegrationConfigurationError):
            ProbeConfig(max_control_events=True)

    def test_invalid_timeout(self):
        with self.assertRaises(IntegrationConfigurationError):
            ProbeConfig(timeout_seconds=0)
        with self.assertRaises(IntegrationConfigurationError):
            ProbeConfig(timeout_seconds=301)
        with self.assertRaises(IntegrationConfigurationError):
            ProbeConfig(timeout_seconds=False)
        with self.assertRaises(IntegrationConfigurationError):
            ProbeConfig(timeout_seconds=True)
        with self.assertRaises(IntegrationConfigurationError):
            ProbeConfig(timeout_seconds=float("nan"))
        with self.assertRaises(IntegrationConfigurationError):
            ProbeConfig(timeout_seconds=float("inf"))
        with self.assertRaises(IntegrationConfigurationError):
            ProbeConfig(timeout_seconds=float("-inf"))

    def test_invalid_bools(self):
        with self.assertRaises(IntegrationConfigurationError):
            ProbeConfig(include_synthetic=1)
        with self.assertRaises(IntegrationConfigurationError):
            ProbeConfig(display_timestamps=0)
        with self.assertRaises(IntegrationConfigurationError):
            ProbeConfig(redact_runtime_identity="yes")


class TestProbeRunner(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.clock_val = 0.0
        def fake_clock():
            return self.clock_val
        self.fake_clock = fake_clock

        self.dummy_event = ControlEvent(
            source_id="test",
            timestamp_ns=1000,
            control=PhysicalControl("button.k01", "A1", ControlKind.BUTTON, None, 1),
            phase=ControlPhase.DOWN,
            transport_code=TransportCode("KEY_F13"),
            synthetic=False,
            reason=None
        )

    async def test_normal_eof(self):
        pipeline = FakePipeline([self.dummy_event])
        config = ProbeConfig(max_control_events=10)
        runner = ProbeRunner(pipeline, config, self.fake_clock)

        self.clock_val = 1.0
        result = await runner.run()

        self.assertEqual(result.termination, ProbeTermination.NORMAL_EOF)
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].sequence, 1)
        self.assertEqual(result.events[0].vendor_name, "A1")

    async def test_event_limit(self):
        pipeline = FakePipeline([self.dummy_event, self.dummy_event, self.dummy_event])
        config = ProbeConfig(max_control_events=2)
        runner = ProbeRunner(pipeline, config, self.fake_clock)

        result = await runner.run()

        self.assertEqual(result.termination, ProbeTermination.EVENT_LIMIT)
        self.assertEqual(len(result.events), 2)
        self.assertTrue(pipeline.closed)

    async def test_timeout(self):
        pipeline = FakePipeline([self.dummy_event], sleep_time=0.2)
        config = ProbeConfig(timeout_seconds=0.05)
        runner = ProbeRunner(pipeline, config, self.fake_clock)

        result = await runner.run()

        self.assertEqual(result.termination, ProbeTermination.TIMEOUT)
        self.assertEqual(len(result.events), 0)
        self.assertTrue(pipeline.closed)

    async def test_observation_error(self):
        pipeline = FakePipeline([])
        pipeline.error_to_raise = ObservationInputError("Failed at /home/user/path")
        config = ProbeConfig()
        runner = ProbeRunner(pipeline, config, self.fake_clock)

        result = await runner.run()

        self.assertEqual(result.termination, ProbeTermination.OBSERVATION_ERROR)
        self.assertEqual(result.error_type, "ObservationInputError")
        self.assertEqual(result.error_message, "Failed at <redacted>/path")
        self.assertTrue(pipeline.closed)

    async def test_cancelled(self):
        pipeline = FakePipeline([])
        pipeline.cancel_to_raise = True
        config = ProbeConfig()
        runner = ProbeRunner(pipeline, config, self.fake_clock)

        with self.assertRaises(asyncio.CancelledError):
            await runner.run()

        self.assertTrue(pipeline.closed)

    async def test_filter_synthetic(self):
        synth_event = ControlEvent(
            source_id="test",
            timestamp_ns=2000,
            control=PhysicalControl("button.k01", "A1", ControlKind.BUTTON, None, 1),
            phase=ControlPhase.UP,
            transport_code=TransportCode("KEY_F13"),
            synthetic=True,
            reason="reset"
        )
        pipeline = FakePipeline([self.dummy_event, synth_event])

        config = ProbeConfig(include_synthetic=False)
        runner = ProbeRunner(pipeline, config, self.fake_clock)
        result = await runner.run()

        self.assertEqual(len(result.events), 1)
        self.assertFalse(result.events[0].synthetic)

        config2 = ProbeConfig(include_synthetic=True)
        runner2 = ProbeRunner(FakePipeline([self.dummy_event, synth_event]), config2, self.fake_clock)
        result2 = await runner2.run()
        self.assertEqual(len(result2.events), 2)

    async def test_total_timeout_is_not_per_event(self):
        # 3 events, each takes 0.03 seconds. Total = 0.09s
        # Config timeout is 0.07s.
        # So it should timeout during the 3rd event, proving it's a total timeout.
        pipeline = FakePipeline([self.dummy_event, self.dummy_event, self.dummy_event], sleep_time=0.03)
        config = ProbeConfig(timeout_seconds=0.07)
        runner = ProbeRunner(pipeline, config, self.fake_clock)

        result = await runner.run()
        self.assertEqual(result.termination, ProbeTermination.TIMEOUT)
        self.assertEqual(len(result.events), 2)
        self.assertTrue(pipeline.closed)

    async def test_event_limit_does_not_evaluate_next(self):
        # We wrap a generator to prove it never requests the 3rd item
        evaluated = 0
        async def generator():
            nonlocal evaluated
            evaluated += 1
            yield self.dummy_event
            evaluated += 1
            yield self.dummy_event
            evaluated += 1
            yield self.dummy_event

        class WrapperPipeline:
            def __init__(self):
                self.closed = False
            def snapshot_diagnostics(self):
                return "fake"
            def observe(self):
                return generator()
            async def close(self):
                self.closed = True

        pipeline = WrapperPipeline()
        config = ProbeConfig(max_control_events=2)
        runner = ProbeRunner(pipeline, config, self.fake_clock)

        result = await runner.run()
        self.assertEqual(result.termination, ProbeTermination.EVENT_LIMIT)
        self.assertEqual(len(result.events), 2)
        self.assertEqual(evaluated, 2)
        self.assertTrue(pipeline.closed)

    async def test_synthetic_filtered_does_not_count_towards_limit(self):
        synth = ControlEvent("test", 0, self.dummy_event.control, ControlPhase.UP, TransportCode("KEY_F13"), True, "test")
        # Sequence: normal, synth, synth, normal, normal
        events = [self.dummy_event, synth, synth, self.dummy_event, self.dummy_event]
        pipeline = FakePipeline(events)
        config = ProbeConfig(max_control_events=2, include_synthetic=False)
        runner = ProbeRunner(pipeline, config, self.fake_clock)

        result = await runner.run()
        self.assertEqual(result.termination, ProbeTermination.EVENT_LIMIT)
        # Should contain the two normal events
        self.assertEqual(len(result.events), 2)
        self.assertEqual(result.events[0].sequence, 1)
        self.assertEqual(result.events[1].sequence, 2)
        self.assertTrue(pipeline.closed)

    async def test_malicious_error_redaction(self):
        pipeline = FakePipeline([])
        msg = "Error opening /home/fieldy/test and /dev/input/event3\nNext line /dev/input/by-id/usb-xxx with serial AABBCCDDEEFF0011"
        pipeline.error_to_raise = ObservationInputError(msg)
        config = ProbeConfig()
        runner = ProbeRunner(pipeline, config, self.fake_clock)

        result = await runner.run()
        self.assertEqual(result.termination, ProbeTermination.OBSERVATION_ERROR)
        self.assertNotIn("/home/fieldy", result.error_message)
        self.assertNotIn("/dev/input", result.error_message)
        self.assertNotIn("AABBCCDDEEFF0011", result.error_message)
        self.assertNotIn("\n", result.error_message)
        self.assertIn("Error opening", result.error_message)

    async def test_programming_error_not_swallowed(self):
        pipeline = FakePipeline([])
        pipeline.error_to_raise = ValueError("Programming error")
        config = ProbeConfig()
        runner = ProbeRunner(pipeline, config, self.fake_clock)

        with self.assertRaises(ValueError):
            await runner.run()
        self.assertTrue(pipeline.closed)

    async def test_formal_event_probe_attribute_error_regression(self):
        # FORMAL EVENT PROBE AttributeError regression
        # 1. Use real ObservationPipeline with fake dependencies
        from yyr4_linux_control.observation.pipeline import ObservationPipeline
        from yyr4_linux_control.observation.interfaces import DeviceSelector, RawInputStreamFactory
        from yyr4_linux_control.device.discovery import YYR4Identity

        class FakeSelector(DeviceSelector):
            def select_single(self) -> YYR4Identity:
                # Need an identity but it won't actually be used successfully if we mock stream
                raise Exception("Should not reach discovery")

        class ErrorSelector(DeviceSelector):
            def select_single(self) -> YYR4Identity:
                from yyr4_linux_control.device.errors import DeviceDiscoveryError
                raise DeviceDiscoveryError("Fake discovery error")

        class FakeInputFactory(RawInputStreamFactory):
            def create(self, identity: YYR4Identity):
                pass

        pipeline = ObservationPipeline(ErrorSelector(), FakeInputFactory())
        config = ProbeConfig(timeout_seconds=0.1)
        runner = ProbeRunner(pipeline, config, self.fake_clock)

        # 2. Execute path that triggered `_pipeline.diagnostics` (any run() does it)
        # We trigger it via a discovery error so it finishes quickly
        result = await runner.run()

        # 3. Prove it no longer raises AttributeError and returns a formal ProbeResult
        self.assertEqual(result.termination, ProbeTermination.OBSERVATION_ERROR)
        self.assertEqual(result.error_type, "ObservationDiscoveryError")
        self.assertIsNotNone(result.diagnostics)
        self.assertEqual(result.diagnostics.discovery_errors, 1)
