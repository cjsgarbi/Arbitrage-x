from .utils.log_config import setup_logging
import logging
import traceback
from datetime import datetime
import json

loggers = setup_logging()
logger = loggers['main_logger']
trade_logger = loggers['trade_logger']
error_logger = loggers['error_logger']
debug_logger = loggers['debug_logger']
critical_logger = loggers['critical_logger']

def log_error(error, context=None):
    """Registra erros com contexto detalhado"""
    error_info = {
        'timestamp': datetime.now().isoformat(),
        'error_type': type(error).__name__,
        'error_message': str(error),
        'traceback': traceback.format_exc(),
        'context': context
    }
    
    error_logger.error(json.dumps(error_info, indent=2))

def log_trade(trade_data):
    """Registra dados de trade em formato JSON"""
    trade_info = {
        'timestamp': datetime.now().isoformat(),
        **trade_data
    }
    trade_logger.info(json.dumps(trade_info, indent=2))

def log_websocket_error(error, connection_info=None):
    """Registra erros de WebSocket com detalhes da conexão"""
    ws_error = {
        'timestamp': datetime.now().isoformat(),
        'error_type': 'WebSocket Error',
        'error_message': str(error),
        'traceback': traceback.format_exc(),
        'connection': connection_info
    }
    error_logger.error(json.dumps(ws_error, indent=2))

def log_api_error(error, endpoint=None, params=None):
    """Registra erros de API com detalhes da requisição"""
    api_error = {
        'timestamp': datetime.now().isoformat(),
        'error_type': 'API Error',
        'error_message': str(error),
        'endpoint': endpoint,
        'params': params,
        'traceback': traceback.format_exc()
    }
    error_logger.error(json.dumps(api_error, indent=2))

def log_cache_metrics(cache_info):
    """Registra métricas do cache"""
    metrics = {
        'timestamp': datetime.now().isoformat(),
        'cache_size': len(cache_info),
        'cache_age': {k: datetime.now().timestamp() - v.get('timestamp', 0) 
                     for k, v in cache_info.items()},
        'update_frequency': {k: v.get('updates_count', 0) 
                           for k, v in cache_info.items()}
    }
    debug_logger.debug(json.dumps(metrics, indent=2))

def log_performance_issue(operation, duration, threshold=1.0):
    """Registra problemas de performance"""
    if duration > threshold:
        perf_info = {
            'timestamp': datetime.now().isoformat(),
            'operation': operation,
            'duration': duration,
            'threshold': threshold
        }
        debug_logger.warning(json.dumps(perf_info, indent=2))

def log_arbitrage_opportunity(opportunity):
    """Registra oportunidades de arbitragem detalhadas"""
    opp_info = {
        'timestamp': datetime.now().isoformat(),
        'route': f"{opportunity.get('a_step_from')}→{opportunity.get('b_step_from')}→{opportunity.get('c_step_from')}",
        'profit': float(opportunity.get('profit', 0)),
        'volume': float(opportunity.get('a_volume', 0)),
        'execution_time': float(opportunity.get('latency', 0)),
        'slippage': float(opportunity.get('slippage', 0)),
        'status': 'identified'
    }
    logger.info(json.dumps(opp_info, indent=2))

def log_critical_error(error, system_state=None):
    """Registra erros críticos que podem afetar o sistema"""
    error_info = {
        'timestamp': datetime.now().isoformat(),
        'error_type': 'Critical Error',
        'error_message': str(error),
        'traceback': traceback.format_exc(),
        'system_state': system_state
    }
    critical_logger.critical(json.dumps(error_info, indent=2))