import unittest
import json
import logging
from datetime import datetime
from pathlib import Path
import tempfile
import shutil
from triangular_arbitrage.utils.log_config import JsonFormatter, setup_logging
from triangular_arbitrage.utils.dashboard_logger import DashboardLogger

class TestLogging(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.loggers = setup_logging(log_dir=Path(self.temp_dir))
        self.dashboard_logger = DashboardLogger(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_json_formatter(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name='test', level=logging.INFO,
            pathname='test.py', lineno=1,
            msg='Test message', args=(),
            exc_info=None
        )
        formatted = formatter.format(record)
        log_dict = json.loads(formatted)
        
        self.assertIn('timestamp', log_dict)
        self.assertIn('level', log_dict)
        self.assertIn('message', log_dict)

    def test_dashboard_logging(self):
        # Testa log de evento
        self.dashboard_logger.log_dashboard_event(
            'test_event',
            {'key': 'value'}
        )
        
        # Testa log de erro
        self.dashboard_logger.log_error(
            'test_error',
            'Error message',
            {'context': 'test'}
        )
        
        # Verifica se os arquivos foram criados
        self.assertTrue(self.dashboard_logger.events_log.exists())
        self.assertTrue(self.dashboard_logger.error_log.exists())

    def test_performance_logging(self):
        metrics = {
            'latency': 100,
            'cache_size': 1000,
            'active_connections': 5
        }
        self.dashboard_logger.log_performance(metrics)
        
        # Verifica estatísticas
        stats = self.dashboard_logger.get_stats()
        self.assertGreater(stats['event_count'], 0)

    def test_null_safety(self):
        # Testa com valores None
        self.dashboard_logger.log_dashboard_event('test', {})
        self.dashboard_logger.log_error('test', 'message', None)
        self.dashboard_logger.log_connection('client1', 'connect', None)
        
        # Não deve lançar exceções
        stats = self.dashboard_logger.get_stats()
        self.assertIsInstance(stats, dict)

if __name__ == '__main__':
    unittest.main()