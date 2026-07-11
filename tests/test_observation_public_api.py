import unittest
import yyr4_linux_control.observation as obs

class TestObservationPublicApi(unittest.TestCase):
    def test_exports(self):
        self.assertTrue(hasattr(obs, "ObservationPipeline"))
        self.assertTrue(hasattr(obs, "ObservationState"))
        self.assertTrue(hasattr(obs, "ObservationDiagnostics"))
        self.assertTrue(hasattr(obs, "DeviceSelector"))
        self.assertTrue(hasattr(obs, "RawInputStream"))
        self.assertTrue(hasattr(obs, "RawInputStreamFactory"))
        self.assertTrue(hasattr(obs, "TransportParserFactory"))
        self.assertTrue(hasattr(obs, "DefaultTransportParserFactory"))
        self.assertTrue(hasattr(obs, "ObservationError"))
        self.assertTrue(hasattr(obs, "ObservationStateError"))
        self.assertTrue(hasattr(obs, "ObservationDiscoveryError"))
        self.assertTrue(hasattr(obs, "ObservationInputError"))
        self.assertTrue(hasattr(obs, "ObservationConfigurationError"))
