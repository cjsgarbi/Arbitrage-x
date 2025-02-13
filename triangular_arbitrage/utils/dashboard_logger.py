from typing import Dict, Optional, Any
import json
import logging
from datetime import datetime
from pathlib import Path
from .log_config import JsonFormatter, setup_logging

class DashboardLogger:
    def __init__(self, log_dir: Optional[str] = None):
        self.log_dir = Path(log_dir) if log_dir else Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # Arquivo de log JSON para eventos do dashboard
        self.events_log = self.log_dir / "dashboard_events.json"
        self.connection_log = self.log_dir / "connections.log"
        self.error_log = self.log_dir / "dashboard_errors.log"
        
        # Inicializa contadores
        self.error_count = 0
        self.warning_count = 0
        self.event_count = 0
        
        # Setup de loggers específicos
        self._setup_loggers()

    def _setup_loggers(self):
        """Configura loggers específicos para diferentes tipos de eventos"""
        # Usa o JsonFormatter existente
        formatter = JsonFormatter()
        
        # Logger para eventos
        self.event_logger = logging.getLogger('dashboard.events')
        event_handler = logging.FileHandler(self.events_log)
        event_handler.setFormatter(formatter)
        self.event_logger.addHandler(event_handler)
        
        # Logger para conexões
        self.conn_logger = logging.getLogger('dashboard.connections')
        conn_handler = logging.FileHandler(self.connection_log)
        conn_handler.setFormatter(formatter)
        self.conn_logger.addHandler(conn_handler)
        
        # Logger para erros
        self.error_logger = logging.getLogger('dashboard.errors')
        error_handler = logging.FileHandler(self.error_log)
        error_handler.setFormatter(formatter)
        self.error_logger.addHandler(error_handler)

    def log_dashboard_event(self, event_type: str, data: Dict[str, Any]):
        """Registra eventos do dashboard"""
        try:
            event = {
                'type': event_type,
                'data': data or {}  # Garante que nunca será None
            }
            self.event_logger.info('Dashboard event', extra={'data': event})
            self.event_count += 1
        except Exception as e:
            self.log_error('event_logging_failed', str(e), {'invalid_data': str(data)})

    def log_connection(self, client_id: str, event: str, details: Optional[Dict[str, Any]] = None):
        """Registra eventos de conexão"""
        try:
            log_data = {
                'client_id': client_id,
                'event': event,
                'details': details or {}  # Garante que nunca será None
            }
            self.conn_logger.info('Connection event', extra={'data': log_data})
        except Exception as e:
            self.log_error('connection_logging_failed', str(e), {'client_id': client_id})

    def log_error(self, error_type: str, message: str, context: Optional[Dict[str, Any]] = None):
        """Registra erros do dashboard"""
        try:
            error_data = {
                'type': error_type,
                'message': message,
                'context': context or {}  # Garante que nunca será None
            }
            self.error_logger.error('Dashboard error', extra={'data': error_data})
            self.error_count += 1
        except Exception as e:
            print(f"Erro crítico no logging: {e}")

    def log_performance(self, metrics: Dict[str, Any]):
        """Registra métricas de performance"""
        try:
            self.log_dashboard_event('performance_metrics', metrics or {})
        except Exception as e:
            self.log_error('performance_logging_failed', str(e), {'metrics': str(metrics)})

    def log_websocket_event(self, event_type: str, client_id: str, data: Optional[Dict[str, Any]] = None):
        """Registra eventos específicos de WebSocket"""
        try:
            event_data = {
                'type': event_type,
                'client_id': client_id,
                'data': data or {}  # Garante que nunca será None
            }
            
            if event_type.startswith('error'):
                self.log_error('websocket_error', str(event_data.get('data', {}).get('error')), {
                    'client_id': client_id,
                    'event_type': event_type
                })
            else:
                self.log_dashboard_event('websocket_event', event_data)
                
        except Exception as e:
            self.log_error('websocket_logging_failed', str(e), {
                'event_type': event_type,
                'client_id': client_id
            })

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de logging"""
        return {
            'error_count': self.error_count,
            'warning_count': self.warning_count,
            'event_count': self.event_count,
            'last_error': self._get_last_error() or {},  # Garante que nunca será None
            'log_files': {
                'events': str(self.events_log),
                'connections': str(self.connection_log),
                'errors': str(self.error_log)
            }
        }

    def _get_last_error(self) -> Optional[Dict[str, Any]]:
        """Retorna o último erro registrado"""
        try:
            if self.error_log.exists():
                with open(self.error_log, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        last_error = json.loads(lines[-1])
                        return {
                            'timestamp': last_error.get('timestamp'),
                            'type': last_error.get('type'),
                            'message': last_error.get('message')
                        }
        except Exception:
            pass
        return {}  # Retorna dict vazio em vez de None

# Cria instância global
dashboard_logger = DashboardLogger()