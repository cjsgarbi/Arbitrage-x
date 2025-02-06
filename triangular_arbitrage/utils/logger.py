import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
import json
import codecs


class Logger:
    def __init__(self, log_dir: str = "logs"):
        """Inicializa o sistema de logs

        Args:
            log_dir: Diretório onde os logs serão salvos
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Configura logger raiz
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.DEBUG)

        # Formata logs
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # Handler para console
        if sys.platform == 'win32':
            console_handler = logging.StreamHandler(
                codecs.getwriter('utf-8')(sys.stdout.buffer))
        else:
            console_handler = logging.StreamHandler(sys.stdout)

        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # Handler para arquivo
        self.setup_file_handler()

        # Arquivo de trades
        self.trade_log = self.log_dir / "trades.json"
        if not self.trade_log.exists():
            self.trade_log.write_text("[]", encoding='utf-8')

    def info(self, message: str):
        """Log nível INFO"""
        self.logger.info(message)

    def warning(self, message: str):
        """Log nível WARNING"""
        self.logger.warning(message)

    def error(self, message: str):
        """Log nível ERROR"""
        self.logger.error(message)

    def debug(self, message: str):
        """Log nível DEBUG"""
        self.logger.debug(message)

    def setup_file_handler(self) -> None:
        """Configura handler para salvar logs em arquivo"""
        now = datetime.now()
        log_file = self.log_dir / f"bot_{now:%Y%m%d_%H%M%S}.log"

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)

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
                'type': error.__class__.__name__
            }

            if context:
                error_data['context'] = context

            error_file = self.log_dir / "errors.json"

            # Carrega erros existentes
            if error_file.exists():
                errors = json.loads(error_file.read_text())
            else:
                errors = []

            # Adiciona novo erro
            errors.append(error_data)

            # Salva arquivo atualizado
            error_file.write_text(json.dumps(
                errors, indent=2), encoding='utf-8')

            self.logger.error(f"Erro registrado: {error}", exc_info=True)

        except Exception as e:
            self.logger.error(f"Erro ao registrar erro: {e}")

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
