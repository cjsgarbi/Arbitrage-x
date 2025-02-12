import logging.handlers
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
import json
import codecs
import locale
from logging.handlers import RotatingFileHandler


def setup_logging():
    """Configura logging com suporte a caracteres especiais no Windows"""
    # Remove handlers existentes
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        
    # Configura formato do log com timestamp mais detalhado
    formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler para console com encoding UTF-8 e detecção do encoding do sistema
    system_encoding = locale.getpreferredencoding()
    console_handler = logging.StreamHandler(
        codecs.getwriter(system_encoding)(sys.stdout.buffer, 'replace')
    )
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # Handler para arquivo com encoding UTF-8
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # Arquivo principal de log com rotação
    main_handler = RotatingFileHandler(
        log_dir / 'bot.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8',
        delay=True
    )
    main_handler.setFormatter(formatter)
    main_handler.setLevel(logging.DEBUG)
    
    # Arquivo específico para erros
    error_handler = RotatingFileHandler(
        log_dir / 'error.log',
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3,
        encoding='utf-8',
        delay=True
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    
    # Configura logger root
    logging.root.setLevel(logging.DEBUG)
    logging.root.addHandler(console_handler)
    logging.root.addHandler(main_handler)
    logging.root.addHandler(error_handler)
    
    # Configura logging para bibliotecas externas
    logging.getLogger('asyncio').setLevel(logging.INFO)
    logging.getLogger('aiohttp').setLevel(logging.INFO)
    logging.getLogger('websockets').setLevel(logging.INFO)
    
    return logging.getLogger(__name__)


class Logger:
    def __init__(self, log_dir: str = "logs"):
        """Inicializa o sistema de logs

        Args:
            log_dir: Diretório onde os logs serão salvos
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.logger = setup_logging()

        # Arquivo de trades
        self.trade_log = self.log_dir / "trades.json"
        if not self.trade_log.exists():
            self.trade_log.write_text("[]", encoding='utf-8')

    def info(self, message: str):
        """Log nível INFO sem emojis"""
        self.logger.info(self._clean_message(message))

    def warning(self, message: str):
        """Log nível WARNING sem emojis"""
        self.logger.warning(self._clean_message(message))

    def error(self, message: str):
        """Log nível ERROR sem emojis"""
        self.logger.error(self._clean_message(message))

    def debug(self, message: str):
        """Log nível DEBUG sem emojis"""
        self.logger.debug(self._clean_message(message))

    def _clean_message(self, message: str) -> str:
        """Remove emojis e caracteres especiais para compatibilidade"""
        return message.encode('ascii', 'ignore').decode('ascii')

    def log_trade(self, trade_data: dict) -> None:
        """Registra informações de um trade

        Args:
            trade_data: Dicionário com informações do trade
        """
        try:
            # Carrega trades existentes
            trades = json.loads(self.trade_log.read_text())

            # Adiciona novo trade
            trade_data['timestamp'] = datetime.now().isoformat()
            trades.append(trade_data)

            # Salva arquivo atualizado
            self.trade_log.write_text(json.dumps(
                trades, indent=2), encoding='utf-8')

            self.logger.info(f"Trade registrado: {trade_data['id']}")

        except Exception as e:
            self.logger.error(f"Erro ao registrar trade: {e}")

    def get_trades(self, limit: Optional[int] = None) -> list:
        """Retorna histórico de trades

        Args:
            limit: Número máximo de trades a retornar

        Returns:
            Lista com histórico de trades
        """
        try:
            trades = json.loads(self.trade_log.read_text())
            if limit:
                trades = trades[-limit:]
            return trades

        except Exception as e:
            self.logger.error(f"Erro ao ler trades: {e}")
            return []

    def clear_trades(self) -> None:
        """Limpa histórico de trades"""
        try:
            self.trade_log.write_text("[]", encoding='utf-8')
            self.logger.info("Histórico de trades limpo")

        except Exception as e:
            self.logger.error(f"Erro ao limpar trades: {e}")

    def log_error(self, error: Exception, context: Optional[dict] = None) -> None:
        """Registra um erro com contexto adicional

        Args:
            error: Exceção ocorrida
            context: Dicionário com informações de contexto
        """
        try:
            error_data = {
                'timestamp': datetime.now().isoformat(),
                'error': str(error),
                'type': error.__class__.__name__,
                'traceback': self._get_traceback(error),
                'context': context or {}
            }

            error_file = self.log_dir / "errors.json"

            # Carrega erros existentes
            if error_file.exists():
                try:
                    errors = json.loads(error_file.read_text(encoding='utf-8'))
                except json.JSONDecodeError:
                    errors = []
            else:
                errors = []

            # Adiciona novo erro
            errors.append(error_data)

            # Mantém apenas os últimos 1000 erros
            if len(errors) > 1000:
                errors = errors[-1000:]

            # Salva arquivo atualizado com formatação
            error_file.write_text(
                json.dumps(errors, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )

            # Logs detalhados do erro
            self.logger.error(
                f"Erro: {error}\nTipo: {error.__class__.__name__}\nContexto: {context}",
                exc_info=True
            )

        except Exception as e:
            self.logger.error(f"Erro ao registrar erro: {e}", exc_info=True)

    def _get_traceback(self, error: Exception) -> str:
        """Retorna o traceback formatado de uma exceção"""
        import traceback
        return ''.join(traceback.format_exception(
            type(error),
            error,
            error.__traceback__
        ))

    def get_errors(self, limit: Optional[int] = None) -> list:
        """Retorna histórico de erros

        Args:
            limit: Número máximo de erros a retornar

        Returns:
            Lista com histórico de erros
        """
        try:
            error_file = self.log_dir / "errors.json"
            if not error_file.exists():
                return []

            errors = json.loads(error_file.read_text())
            if limit:
                errors = errors[-limit:]
            return errors

        except Exception as e:
            self.logger.error(f"Erro ao ler erros: {e}")
            return []
