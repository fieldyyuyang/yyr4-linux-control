import unittest
from yyr4_linux_control.observation.interfaces import DefaultTransportParserFactory
from yyr4_linux_control.transport.parser import TransportParser

class TestObservationInterfaces(unittest.TestCase):
    def test_default_transport_parser_factory(self):
        factory = DefaultTransportParserFactory()
        parser1 = factory.create("test:src")
        parser2 = factory.create("test:src")
        
        self.assertIsInstance(parser1, TransportParser)
        self.assertIsInstance(parser2, TransportParser)
        self.assertIsNot(parser1, parser2)
        self.assertEqual(parser1.source_id, "test:src")
