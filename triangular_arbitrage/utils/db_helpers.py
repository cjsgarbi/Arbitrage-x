import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any
import json
from datetime import datetime
import logging
import os
import aiosqlite
from ..config import DB_CONFIG

logger = logging.getLogger(__name__)


class DBHelpers:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.conn = None  # Será inicializado no setup()
        self.logger.info("✅ DBHelpers inicializado")

    async def setup(self):
        """Configura conexão com banco de dados"""
        try:
            # Cria diretório data se não existir
            if not os.path.exists('data'):
                os.makedirs('data')

            # Conecta ao banco SQLite
            self.conn = sqlite3.connect('data/arbitrage.db')
            self.logger.info("✅ Banco de dados configurado com sucesso")

            # Cria tabelas se não existirem
            await self.create_tables()

        except Exception as e:
            self.logger.error(f"❌ Erro ao configurar banco de dados: {str(e)}")
            if hasattr(self, 'conn') and self.conn:
                self.conn.close()
            raise

    async def create_tables(self):
        """Cria tabelas necessárias"""
        try:
            cursor = self.conn.cursor()

            # Tabela de oportunidades
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS opportunities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    route TEXT NOT NULL,
                    profit REAL NOT NULL,
                    volume REAL NOT NULL,
                    status TEXT NOT NULL,
                    executed INTEGER DEFAULT 0
                )
            ''')

            # Tabela de configurações
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            ''')

            # Tabela de logs
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL
                )
            ''')

            self.conn.commit()
            self.logger.info("✅ Tabelas criadas/verificadas com sucesso")

        except Exception as e:
            self.logger.error(f"❌ Erro ao criar tabelas: {str(e)}")
            raise

    async def save_opportunity(self, opportunity: Dict):
        """Salva uma oportunidade no banco"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT INTO opportunities (
                        timestamp, a_step_from, a_step_to,
                        b_step_from, b_step_to, c_step_from,
                        c_step_to, rate, profit, volume
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    opportunity['timestamp'],
                    opportunity['a_step_from'],
                    opportunity['a_step_to'],
                    opportunity['b_step_from'],
                    opportunity['b_step_to'],
                    opportunity['c_step_from'],
                    opportunity['c_step_to'],
                    opportunity['rate'],
                    opportunity['profit'],
                    opportunity['volume']
                ))
                await db.commit()

        except Exception as e:
            self.logger.error(f"❌ Erro ao salvar oportunidade: {e}")

    async def save_trade(self, trade: Dict):
        """Salva um trade no banco"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT INTO trades (
                        opportunity_id, timestamp,
                        status, profit, error
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (
                    trade.get('opportunity_id'),
                    trade['timestamp'],
                    trade['status'],
                    trade.get('profit'),
                    trade.get('error')
                ))
                await db.commit()

        except Exception as e:
            self.logger.error(f"❌ Erro ao salvar trade: {e}")

    async def get_trades(self, limit: int = 100) -> List[Dict]:
        """Retorna últimos trades"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute('''
                    SELECT * FROM trades
                    SELECT * FROM trades 
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (limit,)) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]

        except Exception as e:
            self.logger.error(f"❌ Erro ao buscar trades: {e}")
            return []

    async def get_opportunities(self, limit: int = 100) -> List[Dict]:
        """Retorna últimas oportunidades"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute('''
                    SELECT * FROM opportunities
                    ORDER BY timestamp DESC
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (limit,)) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]

        except Exception as e:
            self.logger.error(f"❌ Erro ao buscar oportunidades: {e}")
            return []

    async def save_setting(self, key: str, value: str):
        """Salva uma configuração"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT OR REPLACE INTO settings (
                        key, value, updated_at
                    ) VALUES (?, ?, datetime('now'))
                ''', (key, value))
                await db.commit()

        except Exception as e:
            self.logger.error(f"❌ Erro ao salvar configuração: {e}")

    async def get_setting(self, key: str) -> Optional[str]:
        """Retorna valor de uma configuração"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT value FROM settings
                    WHERE key = ?
                ''', (key,)) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else None

        except Exception as e:
            self.logger.error(f"❌ Erro ao buscar configuração: {e}")
            return None

    def save_setting(self, key: str, value: Any) -> None:
        """Salva uma configuração no banco

        Args:
            key: Chave da configuração
            value: Valor a ser salvo (será convertido para JSON)
        """
        try:
            cursor = self.conn.cursor()
            json_value = json.dumps(value)

            cursor.execute("""
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, json_value))

            self.conn.commit()
            logger.debug(f"Configuração salva: {key}")

        except Exception as e:
            logger.error(f"Erro ao salvar configuração {key}: {e}")

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Recupera uma configuração do banco

        Args:
            key: Chave da configuração
            default: Valor padrão se não encontrado

        Returns:
            Valor da configuração ou default
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()

            if row:
                return json.loads(row[0])
            return default

        except Exception as e:
            logger.error(f"Erro ao ler configuração {key}: {e}")
            return default

    def save_trade(self, trade_data: Dict) -> None:
        """Salva informações de um trade

        Args:
            trade_data: Dicionário com dados do trade
        """
        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                INSERT INTO trades (
                    trade_id, symbol, side, quantity, price, total,
                    fee, fee_asset, status, data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_data.get('id'),
                trade_data.get('symbol'),
                trade_data.get('side'),
                trade_data.get('quantity'),
                trade_data.get('price'),
                trade_data.get('total'),
                trade_data.get('fee'),
                trade_data.get('fee_asset'),
                trade_data.get('status'),
                json.dumps(trade_data)
            ))

            self.conn.commit()
            logger.info(f"Trade salvo: {trade_data.get('id')}")

        except Exception as e:
            logger.error(f"Erro ao salvar trade: {e}")

    def get_trades(self, limit: Optional[int] = None) -> List[Dict]:
        """Recupera histórico de trades

        Args:
            limit: Número máximo de trades a retornar

        Returns:
            Lista de trades
        """
        try:
            cursor = self.conn.cursor()

            query = "SELECT data FROM trades ORDER BY created_at DESC"
            if limit:
                query += f" LIMIT {limit}"

            cursor.execute(query)
            return [json.loads(row[0]) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Erro ao ler trades: {e}")
            return []

    def save_opportunity(self, opp_data: Dict) -> None:
        """Salva uma oportunidade de arbitragem

        Args:
            opp_data: Dicionário com dados da oportunidade
        """
        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                INSERT INTO opportunities (
                    a_symbol, b_symbol, c_symbol,
                    rate, profit, volume, data
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                opp_data.get('a_symbol'),
                opp_data.get('b_symbol'),
                opp_data.get('c_symbol'),
                opp_data.get('rate'),
                opp_data.get('profit'),
                opp_data.get('volume'),
                json.dumps(opp_data)
            ))

            self.conn.commit()
            logger.debug("Oportunidade salva")

        except Exception as e:
            logger.error(f"Erro ao salvar oportunidade: {e}")

    def get_opportunities(self, executed: bool = False, limit: Optional[int] = None) -> List[Dict]:
        """Recupera oportunidades de arbitragem

        Args:
            executed: Se True, retorna apenas oportunidades executadas
            limit: Número máximo de oportunidades a retornar

        Returns:
            Lista de oportunidades
        """
        try:
            cursor = self.conn.cursor()

            query = "SELECT data FROM opportunities WHERE executed = ? ORDER BY created_at DESC"
            if limit:
                query += f" LIMIT {limit}"

            cursor.execute(query, (1 if executed else 0,))
            return [json.loads(row[0]) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Erro ao ler oportunidades: {e}")
            return []

    def mark_opportunity_executed(self, opp_id: int) -> None:
        """Marca uma oportunidade como executada

        Args:
            opp_id: ID da oportunidade
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE opportunities SET executed = 1 WHERE id = ?",
                (opp_id,)
            )
            self.conn.commit()
            logger.debug(f"Oportunidade {opp_id} marcada como executada")

        except Exception as e:
            logger.error(f"Erro ao marcar oportunidade {opp_id}: {e}")

    def cleanup_old_data(self, days: int = 30) -> None:
        """Remove dados antigos do banco

        Args:
            days: Número de dias para manter
        """
        try:
            cursor = self.conn.cursor()

            # Remove trades antigos
            cursor.execute(
                "DELETE FROM trades WHERE created_at < date('now', ?)",
                (f"-{days} days",)
            )

            # Remove oportunidades antigas
            cursor.execute(
                "DELETE FROM opportunities WHERE created_at < date('now', ?)",
                (f"-{days} days",)
            )

            self.conn.commit()
            logger.info(f"Dados mais antigos que {days} dias removidos")

        except Exception as e:
            logger.error(f"Erro ao limpar dados antigos: {e}")

    def __del__(self):
        """Fecha conexão ao destruir objeto"""
        try:
            if hasattr(self, 'conn') and self.conn:
                self.conn.close()
                self.logger.info("✅ Conexão com banco de dados fechada")
        except Exception as e:
            self.logger.error(f"❌ Erro ao fechar conexão: {str(e)}")
