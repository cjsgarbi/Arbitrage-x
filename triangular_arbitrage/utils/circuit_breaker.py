"""
Circuit Breaker para proteção contra falhas em cascata
"""
import time
import asyncio
from typing import Callable, Any, Optional, Dict
from enum import Enum
from functools import wraps
from .debug_logger import debug_logger

class CircuitState(Enum):
    CLOSED = "closed"      # Operação normal
    OPEN = "open"         # Bloqueando requisições
    HALF_OPEN = "half_open"  # Testando recuperação

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_timeout: float = 30.0,
        name: str = "default"
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_timeout = half_open_timeout
        
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = CircuitState.CLOSED
        
        self._locks: Dict[str, asyncio.Lock] = {}
        self.metrics = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'state_changes': [],
            'last_error': None
        }
        
        debug_logger.log_event(
            'circuit_breaker_init',
            f'Circuit Breaker {name} inicializado',
            {
                'failure_threshold': failure_threshold,
                'recovery_timeout': recovery_timeout,
                'half_open_timeout': half_open_timeout
            }
        )

    async def get_lock(self, operation: str) -> asyncio.Lock:
        """Obtém lock para operação específica"""
        if operation not in self._locks:
            self._locks[operation] = asyncio.Lock()
        return self._locks[operation]

    def _should_allow_request(self) -> bool:
        """Verifica se requisição deve ser permitida baseado no estado atual"""
        current_time = time.time()
        
        if self.state == CircuitState.CLOSED:
            return True
            
        if self.state == CircuitState.OPEN:
            if current_time - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                debug_logger.log_event(
                    'circuit_state_change',
                    f'Circuit {self.name} mudou para HALF_OPEN',
                    {'previous_state': 'OPEN'}
                )
                return True
            return False
            
        # HALF_OPEN
        if current_time - self.last_failure_time >= self.half_open_timeout:
            return True
        return False

    def _handle_success(self):
        """Processa sucesso da operação"""
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            debug_logger.log_event(
                'circuit_state_change',
                f'Circuit {self.name} mudou para CLOSED',
                {'previous_state': 'HALF_OPEN'}
            )
        
        self.metrics['successful_calls'] += 1
        self.metrics['total_calls'] += 1

    def _handle_failure(self, error: Exception):
        """Processa falha da operação"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        self.metrics['failed_calls'] += 1
        self.metrics['total_calls'] += 1
        self.metrics['last_error'] = str(error)
        
        if self.failure_count >= self.failure_threshold:
            if self.state != CircuitState.OPEN:
                self.state = CircuitState.OPEN
                debug_logger.log_event(
                    'circuit_state_change',
                    f'Circuit {self.name} mudou para OPEN',
                    {
                        'previous_state': 'CLOSED/HALF_OPEN',
                        'failure_count': self.failure_count,
                        'last_error': str(error)
                    }
                )

    def get_metrics(self) -> Dict:
        """Retorna métricas do circuit breaker"""
        return {
            'name': self.name,
            'state': self.state.value,
            'metrics': self.metrics,
            'config': {
                'failure_threshold': self.failure_threshold,
                'recovery_timeout': self.recovery_timeout,
                'half_open_timeout': self.half_open_timeout
            }
        }

def circuit_breaker(breaker: CircuitBreaker, operation: str):
    """
    Decorator para proteger função com circuit breaker
    
    Args:
        breaker: Instância do CircuitBreaker
        operation: Nome da operação para logging
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            if not breaker._should_allow_request():
                debug_logger.log_event(
                    'circuit_blocked',
                    f'Circuit {breaker.name} bloqueou requisição',
                    {'operation': operation, 'state': breaker.state.value}
                )
                raise RuntimeError(f"Circuit {breaker.name} está {breaker.state.value}")
            
            lock = await breaker.get_lock(operation)
            async with lock:
                try:
                    result = await func(*args, **kwargs)
                    breaker._handle_success()
                    return result
                    
                except Exception as e:
                    breaker._handle_failure(e)
                    debug_logger.log_event(
                        'circuit_failure',
                        f'Falha na operação {operation}',
                        {
                            'circuit': breaker.name,
                            'error': str(e),
                            'state': breaker.state.value
                        }
                    )
                    raise
                    
        return wrapper
    return decorator

# Circuit breakers globais para diferentes tipos de operações
api_circuit = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60.0,
    half_open_timeout=30.0,
    name="api_operations"
)