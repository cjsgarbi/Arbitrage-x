"""
Sistema de logging detalhado para debugging
"""
import logging
import json
import os
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path

class DebugLogger:
    def __init__(self, name: str, log_dir: str = "debug_logs"):
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configura logger principal
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Handler para arquivo de log detalhado
        debug_file = self.log_dir / f"{name}_debug_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(debug_file)
        file_handler.setLevel(logging.DEBUG)
        
        # Handler para console com menos detalhes
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatadores
        detailed_formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(module)s:%(lineno)d | %(message)s'
        )
        console_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s'
        )
        
        file_handler.setFormatter(detailed_formatter)
        console_handler.setFormatter(console_formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # Arquivo para dados estruturados
        self.structured_log = self.log_dir / f"{name}_structured_{datetime.now().strftime('%Y%m%d')}.jsonl"

    def log_event(self, 
                 event_type: str, 
                 message: str, 
                 data: Optional[Dict[str, Any]] = None, 
                 level: int = logging.INFO):
        """
        Registra um evento com dados estruturados
        
        Args:
            event_type: Tipo do evento (ex: 'arbitrage_found', 'pair_analysis')
            message: Mensagem descritiva
            data: Dados adicionais do evento
            level: Nível de logging
        """
        try:
            event = {
                'timestamp': datetime.now().isoformat(),
                'event_type': event_type,
                'message': message,
                'data': data or {},
                'level': logging.getLevelName(level)
            }
            
            # Log estruturado
            with open(self.structured_log, 'a') as f:
                f.write(json.dumps(event) + '\n')
            
            # Log regular
            self.logger.log(level, f"{event_type}: {message}")
            
        except Exception as e:
            self.logger.error(f"Erro ao registrar evento: {e}")

    def log_metric(self, 
                  metric_name: str, 
                  value: float, 
                  tags: Optional[Dict[str, str]] = None):
        """
        Registra uma métrica com tags
        """
        try:
            metric = {
                'timestamp': datetime.now().isoformat(),
                'metric': metric_name,
                'value': value,
                'tags': tags or {}
            }
            
            metrics_file = self.log_dir / f"{self.name}_metrics_{datetime.now().strftime('%Y%m%d')}.jsonl"
            
            with open(metrics_file, 'a') as f:
                f.write(json.dumps(metric) + '\n')
                
        except Exception as e:
            self.logger.error(f"Erro ao registrar métrica: {e}")

    def start_operation(self, operation_name: str, context: Optional[Dict] = None) -> str:
        """
        Inicia o logging de uma operação
        """
        operation_id = f"{operation_name}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        self.log_event(
            'operation_started',
            f"Iniciando operação: {operation_name}",
            {
                'operation_id': operation_id,
                'context': context or {}
            }
        )
        
        return operation_id

    def end_operation(self, 
                     operation_id: str, 
                     status: str = 'success', 
                     result: Optional[Dict] = None):
        """
        Finaliza o logging de uma operação
        """
        self.log_event(
            'operation_ended',
            f"Finalizando operação: {operation_id}",
            {
                'operation_id': operation_id,
                'status': status,
                'result': result or {}
            }
        )

    def rotate_logs(self, max_days: int = 7):
        """
        Remove logs antigos
        """
        try:
            cutoff = datetime.now().timestamp() - (max_days * 86400)
            
            for file in self.log_dir.glob('*.*'):
                if file.stat().st_mtime < cutoff:
                    file.unlink()
                    
        except Exception as e:
            self.logger.error(f"Erro ao rotacionar logs: {e}")

# Instância global para uso em todo o projeto
debug_logger = DebugLogger('arbitrage_bot')