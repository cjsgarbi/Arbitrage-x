import os
import shutil
import logging
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import json
import aiosqlite
import gzip
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class BackupManager:
    def __init__(self, 
                 db_path: str,
                 backup_dir: str,
                 config_dir: str,
                 logs_dir: str,
                 retention_days: int = 30,
                 backup_interval: int = 86400):  # 24 horas em segundos
        """Gerenciador de backups

        Args:
            db_path: Caminho do banco de dados
            backup_dir: Diretório para backups
            config_dir: Diretório de configurações
            logs_dir: Diretório de logs
            retention_days: Dias para manter backups
            backup_interval: Intervalo entre backups em segundos
        """
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.config_dir = Path(config_dir)
        self.logs_dir = Path(logs_dir)
        self.retention_days = retention_days
        self.backup_interval = backup_interval

        # Cria diretórios se não existirem
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        for subdir in ['db', 'config', 'logs']:
            (self.backup_dir / subdir).mkdir(exist_ok=True)

        logger.info(f"✅ Sistema de backup inicializado - Retenção: {retention_days} dias")
        self._running = True
        self._backup_task = None

    async def start_backup_loop(self):
        """Inicia loop de backup automático"""
        self._running = True
        while self._running:
            try:
                await self.perform_backup()
                # Alterando para versão assíncrona
                await self._cleanup_old_backups()
                await asyncio.sleep(self.backup_interval)
            except Exception as e:
                logger.error(f"❌ Erro no loop de backup: {e}")
                await asyncio.sleep(300)  # Espera 5 minutos em caso de erro

    async def stop(self):
        """Para o backup manager e realiza backup final"""
        try:
            self._running = False
            
            # Realiza um backup final
            logger.info("Realizando backup final antes de parar...")
            await self.perform_backup()
            
            # Cancela task de backup se estiver rodando
            if self._backup_task and not self._backup_task.done():
                self._backup_task.cancel()
                try:
                    # Aguarda a task ser cancelada
                    await asyncio.wait_for(asyncio.shield(self._backup_task), timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
                
            logger.info("✅ Backup Manager parado com sucesso")
        except Exception as e:
            logger.error(f"❌ Erro ao parar Backup Manager: {e}")
            raise

    async def perform_backup(self) -> bool:
        """Executa backup completo do sistema

        Returns:
            bool: True se backup foi bem sucedido
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            # Backup do banco de dados
            db_backup = await self._backup_database(timestamp)
            
            # Backup das configurações
            config_backup = await self._backup_configs(timestamp)
            
            # Backup dos logs
            logs_backup = await self._backup_logs(timestamp)
            
            # Registro do backup
            manifest = {
                'timestamp': timestamp,
                'database': str(db_backup) if db_backup else None,
                'configs': str(config_backup) if config_backup else None,
                'logs': str(logs_backup) if logs_backup else None,
                'retention_days': self.retention_days
            }
            
            manifest_path = self.backup_dir / f"manifest_{timestamp}.json"
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            
            logger.info(f"✅ Backup completo realizado: {timestamp}")
            return True

        except Exception as e:
            logger.error(f"❌ Erro ao realizar backup: {e}")
            return False

    async def _backup_database(self, timestamp: str) -> Optional[Path]:
        """Realiza backup do banco de dados

        Args:
            timestamp: Timestamp para nome do arquivo

        Returns:
            Path: Caminho do arquivo de backup ou None se falhou
        """
        try:
            backup_path = self.backup_dir / 'db' / f"arbitrage_{timestamp}.db.gz"
            
            # Garante que o diretório pai existe
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            async with aiosqlite.connect(self.db_path) as db:
                # Backup em memória primeiro
                # Lista tabelas
                async with db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'") as cursor:
                    tables = [row[0] for row in await cursor.fetchall()]
                
                schema = []
                data = []
                
                for table_name in tables:
                    # Pega o schema real da tabela
                    async with db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,)) as cursor:
                        create_sql = await cursor.fetchone()
                        if create_sql and create_sql[0]:
                            schema.append(create_sql[0])
                            # Pega dados de forma segura
                            async with db.execute(f"SELECT * FROM [{table_name}]") as cursor:
                                rows = await cursor.fetchall()
                                data.append({
                                    'table': table_name,
                                    'rows': [list(row) for row in rows]  # Converte para lista
                                })
                
                # Comprime e salva
                with gzip.open(backup_path, 'wt') as f:
                    backup_data = {
                        'schema': schema,
                        'data': data
                    }
                    json.dump(backup_data, f)
                
            logger.info(f"✅ Backup do banco realizado: {backup_path}")
            return backup_path

        except Exception as e:
            logger.error(f"❌ Erro ao backup do banco: {e}")
            return None

    async def _backup_configs(self, timestamp: str) -> Optional[Path]:
        """Realiza backup das configurações

        Args:
            timestamp: Timestamp para nome do arquivo

        Returns:
            Path: Caminho do arquivo de backup ou None se falhou
        """
        try:
            backup_path = self.backup_dir / 'config' / f"config_{timestamp}.tar.gz"
            
            # Cria arquivo tar.gz com configs
            shutil.make_archive(
                str(backup_path).replace('.gz', ''),
                'gztar',
                self.config_dir
            )
            
            logger.info(f"✅ Backup de configs realizado: {backup_path}")
            return backup_path

        except Exception as e:
            logger.error(f"❌ Erro ao backup de configs: {e}")
            return None

    async def _backup_logs(self, timestamp: str) -> Optional[Path]:
        """Realiza backup dos logs

        Args:
            timestamp: Timestamp para nome do arquivo

        Returns:
            Path: Caminho do arquivo de backup ou None se falhou
        """
        try:
            backup_path = self.backup_dir / 'logs' / f"logs_{timestamp}.tar.gz"
            
            # Cria arquivo tar.gz com logs
            shutil.make_archive(
                str(backup_path).replace('.gz', ''),
                'gztar',
                self.logs_dir
            )
            
            logger.info(f"✅ Backup de logs realizado: {backup_path}")
            return backup_path

        except Exception as e:
            logger.error(f"❌ Erro ao backup de logs: {e}")
            return None

    async def _cleanup_old_backups(self):
        """Remove backups antigos baseado na retenção de forma assíncrona"""
        try:
            cutoff = datetime.now() - timedelta(days=self.retention_days)
            
            for subdir in ['db', 'config', 'logs']:
                path = self.backup_dir / subdir
                for file in path.glob('*'):
                    try:
                        # Extrai timestamp do nome do arquivo
                        timestamp = datetime.strptime(
                            file.stem.split('_')[1], 
                            "%Y%m%d_%H%M%S"
                        )
                        
                        if timestamp < cutoff:
                            # Usa função assíncrona para remoção do arquivo
                            await asyncio.to_thread(file.unlink)
                            logger.debug(f"🗑️ Removido backup antigo: {file}")
                    except Exception as e:
                        logger.error(f"❌ Erro ao processar arquivo {file}: {e}")
                        continue
            
            # Limpa manifestos antigos
            for manifest in self.backup_dir.glob('manifest_*.json'):
                try:
                    timestamp = datetime.strptime(
                        manifest.stem.split('_')[1],
                        "%Y%m%d_%H%M%S"
                    )
                    if timestamp < cutoff:
                        # Usa função assíncrona para remoção do manifesto
                        await asyncio.to_thread(manifest.unlink)
                except Exception as e:
                    logger.error(f"❌ Erro ao processar manifesto {manifest}: {e}")
                    continue

        except Exception as e:
            logger.error(f"❌ Erro na limpeza de backups: {e}")

    async def restore_backup(self, timestamp: str) -> bool:
        """Restaura backup específico

        Args:
            timestamp: Timestamp do backup a restaurar

        Returns:
            bool: True se restauração foi bem sucedida
        """
        try:
            manifest_path = self.backup_dir / f"manifest_{timestamp}.json"
            if not manifest_path.exists():
                raise ValueError(f"Manifesto não encontrado: {manifest_path}")
            
            with open(manifest_path) as f:
                manifest = json.load(f)
            
            # Restaura banco
            if manifest['database']:
                db_path = Path(manifest['database'])
                if db_path.exists():
                    with gzip.open(db_path, 'rt') as f:
                        backup_data = json.load(f)
                        
                    async with aiosqlite.connect(self.db_path) as db:
                        # Recria schema
                        for sql in backup_data['schema']:
                            await db.execute(sql)
                        
                        # Restaura dados
                        for table_data in backup_data['data']:
                            table = table_data['table']
                            for row in table_data['rows']:
                                placeholders = ','.join(['?' for _ in row])
                                sql = f"INSERT INTO {table} VALUES ({placeholders})"
                                await db.execute(sql, row)
                        
                        await db.commit()
            
            # Restaura configs
            if manifest['configs']:
                config_path = Path(manifest['configs'])
                if config_path.exists():
                    shutil.unpack_archive(
                        config_path,
                        self.config_dir,
                        'gztar'
                    )
            
            # Restaura logs
            if manifest['logs']:
                logs_path = Path(manifest['logs'])
                if logs_path.exists():
                    shutil.unpack_archive(
                        logs_path,
                        self.logs_dir,
                        'gztar'
                    )
            
            logger.info(f"✅ Backup restaurado com sucesso: {timestamp}")
            return True

        except Exception as e:
            logger.error(f"❌ Erro ao restaurar backup: {e}")
            return False

    async def list_backups(self) -> List[Dict]:
        """Lista todos os backups disponíveis

        Returns:
            List[Dict]: Lista de backups com detalhes
        """
        try:
            backups = []
            for manifest in sorted(self.backup_dir.glob('manifest_*.json')):
                with open(manifest) as f:
                    backup_info = json.load(f)
                    backups.append(backup_info)
            return backups

        except Exception as e:
            logger.error(f"❌ Erro ao listar backups: {e}")
            return []