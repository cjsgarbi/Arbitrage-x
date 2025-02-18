"""
Gerenciamento centralizado de erros para o sistema de arbitragem
"""
import logging
import traceback
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from functools import wraps

logger = logging.getLogger(__name__)

class ArbitrageError(Exception):
    """Classe base para erros de arbitragem"""
    def __init__(self, message: str, error_code: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}
        self.timestamp = datetime.now()

class APIError(ArbitrageError):
    """Erros relacionados a chamadas de API"""
    pass

class WebSocketError(ArbitrageError):
    """Erros relacionados a conexões WebSocket"""
    pass

class ValidationError(ArbitrageError):
    """Erros de validação de dados"""
    pass

class DatabaseError(ArbitrageError):
    """Erros relacionados ao banco de dados"""
    pass

def handle_errors(retries: int = 3, delay: float = 1.0):
    """
    Decorator para tratamento de erros com retry
    
    Args:
        retries: Número máximo de tentativas
        delay: Tempo entre tentativas em segundos
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except ArbitrageError as e:
                    logger.error(f"Erro de arbitragem: {e.error_code} - {str(e)}")
                    logger.error(f"Detalhes: {e.details}")
                    last_error = e
                    if attempt < retries - 1:
                        await asyncio.sleep(delay * (attempt + 1))
                    continue
                except Exception as e:
                    logger.error(f"Erro não tratado: {str(e)}")
                    logger.error(f"Stack trace: {traceback.format_exc()}")
                    last_error = e
                    if attempt < retries - 1:
                        await asyncio.sleep(delay * (attempt + 1))
                    continue
            
            if last_error:
                raise last_error
        return wrapper
    return decorator

class ErrorTracker:
    """Rastreia e analisa erros do sistema"""
    def __init__(self):
        self.error_counts: Dict[str, int] = {}
        self.error_history: List[Dict] = []
        self.max_history = 1000
    
    def track_error(self, error: Exception, context: Optional[Dict] = None):
        """Registra um erro para análise"""
        error_type = type(error).__name__
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        
        error_entry = {
            'type': error_type,
            'message': str(error),
            'timestamp': datetime.now(),
            'context': context or {},
            'stack_trace': traceback.format_exc()
        }
        
        self.error_history.append(error_entry)
        if len(self.error_history) > self.max_history:
            self.error_history = self.error_history[-self.max_history:]
    
    def get_error_stats(self) -> Dict:
        """Retorna estatísticas de erros"""
        return {
            'total_errors': sum(self.error_counts.values()),
            'error_counts': self.error_counts,
            'recent_errors': self.error_history[-10:] if self.error_history else []
        }
    
    def clear_history(self):
        """Limpa histórico de erros"""
        self.error_counts.clear()
        self.error_history.clear()

# Instância global do rastreador de erros
error_tracker = ErrorTracker()