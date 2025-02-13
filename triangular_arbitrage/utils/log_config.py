import logging
import logging.handlers
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import json
import shutil
from typing import Dict, Optional, Any, Union

class LogPath:
    """Classe auxiliar para gerenciar paths de log com validação de tipo"""
    @staticmethod
    def validate(path: Optional[Union[str, Path]] = None) -> Path:
        """Converte e valida path"""
        if path is None:
            return Path("logs")
        return Path(path)

    @staticmethod
    def ensure_dir(path: Path) -> None:
        """Garante que o diretório existe"""
        path.mkdir(exist_ok=True)

class JsonFormatter(logging.Formatter):
    """Formatador personalizado para logs em JSON"""
    def format(self, record):
        log_obj = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage()
        }
        
        # Adiciona exceção se existir
        if record.exc_info:
            log_obj['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info and record.exc_info[0] else 'None',
                'message': str(record.exc_info[1]),
                'traceback': self.formatException(record.exc_info)
            }
            
        # Adiciona dados extras se existirem
        if hasattr(record, 'data'):
            if 'data' in record.__dict__:
                log_obj['data'] = record.__dict__.get('data', None)
            
        return json.dumps(log_obj)

def check_disk_space(path: Path) -> Dict[str, Any]:
    """Verifica espaço em disco disponível para logs"""
    try:
        total, used, free = shutil.disk_usage(path)
        free_mb = free // (1024 * 1024)
        return {
            'total_mb': total // (1024 * 1024),
            'used_mb': used // (1024 * 1024),
            'free_mb': free_mb,
            'is_critical': free_mb < 500
        }
    except Exception as e:
        logging.error(f"Erro ao verificar espaço em disco: {e}")
        return {'error': str(e)}

def cleanup_old_logs(log_path: Path, max_age_days: int = 1) -> None:
    """Remove logs mais antigos que max_age_days"""
    try:
        cutoff = datetime.now() - timedelta(days=max_age_days)
        for file in log_path.glob('*.log*'):
            if file.stat().st_mtime < cutoff.timestamp():
                file.unlink()
                logging.info(f"Log antigo removido: {file.name}")
    except Exception as e:
        logging.error(f"Erro na limpeza de logs: {e}")

def setup_logging(name: str = "arbitrage", log_dir: Optional[Union[str, Path]] = None) -> Dict[str, logging.Logger]:
    """Configura sistema de logging detalhado com validação e formatação JSON"""
    
    # Configura diretório de logs
    log_dir = Path(log_dir) if log_dir else Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Verifica espaço em disco
    disk_status = check_disk_space(log_dir)
    if disk_status.get('is_critical', False):
        cleanup_old_logs(log_dir)
    
    # Formatador JSON
    json_formatter = JsonFormatter()
    
    # Handler para logs gerais
    main_log_path = Path(log_dir).joinpath(f"{name}.log")
    main_handler = logging.handlers.RotatingFileHandler(
        str(main_log_path),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    main_handler.setFormatter(json_formatter)
    
    # Handler para erros
    error_log_path = Path(log_dir).joinpath("error.log")
    error_handler = logging.handlers.RotatingFileHandler(
        str(error_log_path),
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setFormatter(json_formatter)
    error_handler.setLevel(logging.ERROR)
    
    # Handler para debug
    debug_log_path = Path(log_dir).joinpath(f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    debug_handler = logging.handlers.RotatingFileHandler(
        str(debug_log_path),
        maxBytes=10*1024*1024,
        backupCount=2,
        encoding='utf-8'
    )
    debug_handler.setFormatter(json_formatter)
    debug_handler.setLevel(logging.DEBUG)
    
    # Handler para trades
    trade_log_path = Path(log_dir).joinpath("trades.json")
    trade_handler = logging.handlers.RotatingFileHandler(
        str(trade_log_path),
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    trade_handler.setFormatter(json_formatter)
    
    # Handler para console com cores
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | \x1b[36m%(message)s\x1b[0m'
        )
    )
    
    # Configura logger raiz
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Remove handlers antigos
    root_logger.handlers.clear()
    
    # Adiciona novos handlers
    root_logger.addHandler(main_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(debug_handler)
    root_logger.addHandler(console_handler)
    
    # Configura logger específico para trades
    trade_logger = logging.getLogger("trades")
    trade_logger.addHandler(trade_handler)
    trade_logger.setLevel(logging.INFO)
    
    # Configura outros loggers específicos
    performance_logger = logging.getLogger("performance")
    performance_logger.setLevel(logging.INFO)
    
    websocket_logger = logging.getLogger("websocket")
    websocket_logger.setLevel(logging.INFO)
    
    api_logger = logging.getLogger("api")
    api_logger.setLevel(logging.INFO)
    
    def handle_exception(exc_type, exc_value, exc_traceback):
        """Handler para exceções não tratadas"""
        if issubclass(exc_type, KeyboardInterrupt):
            # Não loga KeyboardInterrupt
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        root_logger.critical(
            "Exceção não tratada",
            exc_info=(exc_type, exc_value, exc_traceback)
        )
    
    # Registra handler para exceções não tratadas
    sys.excepthook = handle_exception
    
    # Retorna dicionário com todos os loggers configurados
    return {
        'root': root_logger,
        'trade': trade_logger,
        'performance': performance_logger,
        'websocket': websocket_logger,
        'api': api_logger,
        'error': logging.getLogger("error"),
        'debug': logging.getLogger("debug")
    }

# Configurações adicionais
LOG_COLORS = {
    'DEBUG': '\x1b[36m',    # Ciano
    'INFO': '\x1b[32m',     # Verde
    'WARNING': '\x1b[33m',  # Amarelo
    'ERROR': '\x1b[31m',    # Vermelho
    'CRITICAL': '\x1b[41m', # Fundo vermelho
}

LOG_LEVELS = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}

# Exporta configurações
__all__ = ['setup_logging', 'LOG_COLORS', 'LOG_LEVELS', 'JsonFormatter']