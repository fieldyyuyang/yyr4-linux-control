import asyncio
import unittest
from unittest.mock import patch, MagicMock

from yyr4_linux_control.daemon.session import ProductionInputSessionFactory

class FakePipeline:
    def __init__(self):
        self.closed = False
    async def observe(self):
        if False: yield
    async def close(self):
        self.closed = True

class TestDaemonProduction(unittest.IsolatedAsyncioTestCase):
    @patch('yyr4_linux_control.daemon.session.build_linux_observation_pipeline')
    async def test_production_session_factory_uses_existing_observation_composition(self, mock_build):
        mock_comp = MagicMock()
        mock_pipeline = FakePipeline()
        mock_comp.pipeline = mock_pipeline
        mock_build.return_value = mock_comp
        
        factory = ProductionInputSessionFactory(include_mouse=True)
        session = factory.create_session()
        
        # Start observing to trigger build
        async for _ in session.observe(): pass
        
        mock_build.assert_called_once_with(include_mouse=True)
        self.assertIsNotNone(session)

    @patch('yyr4_linux_control.daemon.session.build_linux_observation_pipeline')
    async def test_production_session_factory_creates_new_pipeline_per_reconnect(self, mock_build):
        mock_comp = MagicMock()
        mock_pipeline = FakePipeline()
        mock_comp.pipeline = mock_pipeline
        mock_build.return_value = mock_comp
        
        factory = ProductionInputSessionFactory(include_mouse=False)
        sess1 = factory.create_session()
        sess2 = factory.create_session()
        
        async for _ in sess1.observe(): pass
        async for _ in sess2.observe(): pass
        
        self.assertEqual(mock_build.call_count, 2)
        self.assertNotEqual(sess1, sess2)

    @patch('yyr4_linux_control.daemon.session.build_linux_observation_pipeline')
    async def test_production_session_closes_pipeline_on_eof(self, mock_build):
        mock_comp = MagicMock()
        mock_pipeline = FakePipeline()
        mock_comp.pipeline = mock_pipeline
        mock_build.return_value = mock_comp
        
        factory = ProductionInputSessionFactory()
        session = factory.create_session()
        
        events = [e async for e in session.observe()]
        self.assertEqual(len(events), 0)

    @patch('yyr4_linux_control.daemon.session.build_linux_observation_pipeline')
    async def test_production_session_closes_pipeline_on_cancellation(self, mock_build):
        mock_comp = MagicMock()
        mock_pipeline = FakePipeline()
        mock_comp.pipeline = mock_pipeline
        mock_build.return_value = mock_comp
        
        factory = ProductionInputSessionFactory()
        session = factory.create_session()
        
        async for _ in session.observe(): pass
        await session.close()
        self.assertTrue(mock_pipeline.closed)
