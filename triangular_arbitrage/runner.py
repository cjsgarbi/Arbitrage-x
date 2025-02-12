import asyncio
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

from .core.bot_core import BotCore
from .utils.logger import Logger
from .utils.db_helpers import DBHelpers
from .ui.display import Display
from .ui.web.app import WebDashboard

logger = logging.getLogger(__name__)

class ArbitrageRunner:
    def __init__(self):
        # Carrega variáveis de ambiente
        load_dotenv()
        
        # Configura logger
        self.logger = Logger().logger
        self.logger.setLevel(logging.INFO)
        
        # Prepara configuração base
        self.config = {
            'BINANCE_API_KEY': os.getenv('BINANCE_API_KEY', '').strip().replace('"', ''),
            'BINANCE_API_SECRET': os.getenv('BINANCE_API_SECRET', '').strip().replace('"', ''),
            'TEST_MODE': True,  # Modo de teste por padrão
            'SAVE_DATA': True   # Salvar dados para análise
        }
        
        self.display = None
        self.db = None
        self.bot = None
        self.dashboard = None
        
    async def initialize(self):
        """Inicializa todos os componentes do sistema"""
        try:
            # Inicializa display
            self.display = Display()
            self.logger.info("✅ Display inicializado")
            
            # Inicializa banco de dados
            self.db = DBHelpers()
            await self.db.setup()
            self.logger.info("✅ Banco de dados inicializado")
            
            # Inicializa bot core
            self.bot = BotCore(db=self.db, display=self.display, config=self.config)
            await self.bot.init()  # Inicializa componentes internos
            self.logger.info("✅ Bot core inicializado")
            
            # Inicializa dashboard web
            self.dashboard = WebDashboard(self.bot)
            self.logger.info("✅ Dashboard web inicializado")
            
        except Exception as e:
            self.logger.error(f"❌ Erro na inicialização: {e}")
            raise
            
    async def start(self):
        """Inicia o sistema"""
        # Configura servidor web
        import uvicorn
        config = uvicorn.Config(
            self.dashboard.app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )
        server = uvicorn.Server(config)
        
        # Inicia bot e servidor web
        try:
            await asyncio.gather(
                self.bot.start(),
                server.serve()
            )
        except Exception as e:
            self.logger.error(f"❌ Erro ao executar: {e}")
            raise
            
    async def stop(self):
        """Para o sistema graciosamente"""
        try:
            if self.bot:
                await self.bot.stop()
            if self.db:
                await self.db.close()
            self.logger.info("✅ Sistema encerrado com sucesso")
        except Exception as e:
            self.logger.error(f"❌ Erro ao encerrar: {e}")
            raise

def run():
    """Função principal para executar o sistema"""
    # Configura event loop para Windows
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Cria e executa runner
    runner = ArbitrageRunner()
    
    async def main():
        await runner.initialize()
        await runner.start()
        
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Encerrando sistema...")
        asyncio.run(runner.stop())
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        asyncio.run(runner.stop())
        raise