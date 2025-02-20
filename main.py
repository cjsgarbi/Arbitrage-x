import asyncio
import sys
import os
import signal
from functools import partial
import logging
from dotenv import load_dotenv  # Corrigido: importação correta do python-dotenv

from triangular_arbitrage.core.bot_core import BotCore
from triangular_arbitrage.core.ai_pair_finder import AIPairFinder
from triangular_arbitrage.ui.web.app import WebDashboard
from triangular_arbitrage.utils.error_handler import error_tracker
from triangular_arbitrage.utils.logger import Logger
from triangular_arbitrage.utils.debug_logger import debug_logger

import uvicorn  # Importação padrão do uvicorn

logger = logging.getLogger(__name__)

# Carrega variáveis de ambiente
load_dotenv()

async def init_components():
    """Inicializa componentes essenciais do sistema"""
    try:
        # Configurações básicas
        config = {
            'BINANCE_API_KEY': os.getenv('BINANCE_API_KEY'),
            'BINANCE_API_SECRET': os.getenv('BINANCE_API_SECRET')
        }
        
        # Inicializa IA
        debug_logger.log_event('init', 'Iniciando IA')
        ai_finder = AIPairFinder(config)
        
        # Inicializa bot com IA
        debug_logger.log_event('init', 'Iniciando Bot Core')
        bot = BotCore(config=config)  # Passando config aqui
        await bot.initialize()
        
        # Inicializa dashboard
        debug_logger.log_event('init', 'Iniciando Web Dashboard')
        dashboard = WebDashboard(bot)
        await dashboard.initialize()
        
        return bot, dashboard

    except Exception as e:
        error_tracker.track_error(e)
        logger.error(f"Erro ao inicializar componentes: {e}")
        raise

async def cleanup(bot, dashboard):
    """Limpa recursos essenciais"""
    try:
        if bot:
            await bot.stop()
        if dashboard:
            await dashboard.cleanup()
            
    except Exception as e:
        error_tracker.track_error(e)
        logger.error(f"Erro ao limpar recursos: {e}")
    finally:
        loop = asyncio.get_event_loop()
        loop.stop()
        os._exit(0)

def handle_shutdown(bot, dashboard, loop, signal_name):
    """Handler para sinais de finalização"""
    logger.info(f"Recebido sinal de finalização: {signal_name}")
    loop.create_task(cleanup(bot, dashboard))

async def main():
    bot = None
    dashboard = None
    try:
        # Inicializa logger
        Logger()
        logger.info("Iniciando sistema de arbitragem...")

        # Inicializa componentes
        bot, dashboard = await init_components()
        
        if not bot or not dashboard:
            raise Exception("Falha na inicialização dos componentes")

        # Configura servidor web
        config = uvicorn.Config(
            app=dashboard.app,
            host="127.0.0.1",
            port=8000,
            log_level="info",
            workers=1,
            ws_ping_interval=20.0,
            ws_ping_timeout=30.0
        )
        server = uvicorn.Server(config)

        # Configura loop principal
        loop = asyncio.get_event_loop()
        
        # Configura handlers de shutdown
        if sys.platform == "win32":
            def win_handler(type, value, traceback):
                if isinstance(value, KeyboardInterrupt):
                    asyncio.create_task(cleanup(bot, dashboard))
            sys.excepthook = win_handler
        else:
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(
                    sig,
                    partial(handle_shutdown, bot, dashboard, loop, sig.name)
                )

        # Inicia bot e servidor
        try:
            server_task = asyncio.create_task(server.serve())
            bot_task = asyncio.create_task(bot.start())
            
            await asyncio.wait(
                [server_task, bot_task],
                return_when=asyncio.FIRST_COMPLETED
            )

        except asyncio.CancelledError:
            logger.info("Tasks canceladas, iniciando shutdown...")
            
    except KeyboardInterrupt:
        logger.info("Interrupção detectada, encerrando...")
        await cleanup(bot, dashboard)
    except Exception as e:
        error_tracker.track_error(e)
        logger.error(f"Erro fatal: {e}")
    finally:
        os._exit(0)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
