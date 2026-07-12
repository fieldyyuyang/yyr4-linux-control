"""Tests for the integration public API."""

from __future__ import annotations

import unittest

class TestIntegrationPublicApi(unittest.TestCase):

    def test_integration_exports(self):
        import yyr4_linux_control.integration as integration
        
        expected_exports = [
            "RuntimePreflight",
            "DependencyStatus",
            "PermissionCheck",
            "IdentityPermissionChecker",
            "FilesystemIdentityPermissionChecker",
            "check_runtime_preflight",
            
            "IntegrationError",
            "IntegrationConfigurationError",
            "IntegrationDependencyError",
            "IntegrationPermissionError",
            "IntegrationSafetyError",
            "ProbeError",
            "ProbeTimeoutError",
            "ProbeLimitReached",
            
            "LinuxRawInputStreamFactory",
            "LinuxObservationComposition",
            "build_linux_observation_pipeline",
            
            "ProbeAuthorization",
            "ProbeConfig",
            "ProbeEvent",
            "ProbeResult",
            "ProbeTermination",
            "ProbeRunner",
            "validate_probe_authorization",
        ]
        
        for name in expected_exports:
            self.assertTrue(hasattr(integration, name), f"Missing export: {name}")

    def test_root_exports(self):
        import yyr4_linux_control as root
        
        expected_root_exports = [
            "RuntimePreflight",
            "ProbeConfig",
            "ProbeResult",
            "ProbeRunner",
        ]
        
        for name in expected_root_exports:
            self.assertTrue(hasattr(root, name), f"Missing root export: {name}")
