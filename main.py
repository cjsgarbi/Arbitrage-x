import asyncio
import sys
import os
import signal
import traceback
from triangular_arbitrage.utils.logger import Logger
from triangular_arbitrage.core.bot_core import BotCore
from triangular_arbitrage.ui.web.app import WebDashboard
import uvicorn
import logging
from triangular_arbitrage.config import DB_CONFIG, DISPLAY_CONFIG
from dotenv import load_dotenv
from functools import partial

logger = logging.getLogger(__name__)

# Carrega variáveis de ambiente
load_dotenv()

async def init_components():
    """Inicializa componentes do sistema"""
    try:
        # Configura componentes necessários
        db = DB_CONFIG
        display = DISPLAY_CONFIG
        config = {
            'BINANCE_API_KEY': os.getenv('BINANCE_API_KEY'),
            'BINANCE_API_SECRET': os.getenv('BINANCE_API_SECRET'),
            'test_mode': True  # Modo de teste por padrão
        }
        
        # Cria instância do bot com configurações corretas
        bot = BotCore(db=db, display=display, config=config)
        
        # Inicia o bot
        await bot.initialize()
        
        # Inicia o dashboard
        dashboard = WebDashboard(bot)
        await dashboard.initialize()
        
        return bot, dashboard
    except Exception as e:
        logger.error(f"Erro ao inicializar componentes: {e}")
        raise

def handle_shutdown(bot, dashboard, loop, signal_name):
    """Handler para sinais de finalização"""
    logger.info(f"Recebido sinal de finalização: {signal_name}")
    
    # Cancela todas as tasks pendentes
    for task in asyncio.all_tasks(loop):
        if task is not asyncio.current_task():
            task.cancel()
    
    # Agenda a finalização do bot e dashboard
    loop.create_task(cleanup(bot, dashboard))

async def cleanup(bot, dashboard):
    """Limpa recursos e finaliza componentes"""
    try:
        if bot:
            await bot.stop()
        if dashboard:
            await dashboard.cleanup()
        logger.info("✅ Sistema encerrado com sucesso")
    except Exception as cleanup_error:
        logger.error(f"Erro ao limpar recursos: {str(cleanup_error)}")
    finally:
        # Força a parada do loop de eventos
        asyncio.get_event_loop().stop()

async def main():
    bot = None
    dashboard = None
    try:
        # Inicializa logger
        Logger()
        logger.info("Bot de Arbitragem Triangular")
        logger.info("Iniciando sistema...")

        # Inicializa componentes com retry
        bot, dashboard = await init_components()

        if not bot or not dashboard:
            raise Exception("Falha na inicialização dos componentes")

        # Configura servidor web com recuperação de erros
        config = uvicorn.Config(
            app=dashboard.app,
            host="127.0.0.1",
            port=8000,
            log_level="info",
            reload=False,
            workers=1,
            timeout_keep_alive=30,
            loop="auto",
            lifespan="on",
            access_log=False
        )
        server = uvicorn.Server(config)

        # Configura loop principal com tratamento de exceções
        loop = asyncio.get_event_loop()
        loop.set_exception_handler(lambda loop, context: logger.error(f"Erro assíncrono: {context}"))
        
        # No Windows, usamos um handler de exceção ao invés de sinais
        if sys.platform == "win32":
            def win_handler(type, value, traceback):
                if isinstance(value, KeyboardInterrupt):
                    asyncio.create_task(cleanup(bot, dashboard))
                else:
                    sys.__excepthook__(type, value, traceback)
            
            sys.excepthook = win_handler
        else:
            # Em sistemas Unix, usa handlers de sinal
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(
                    sig,
                    partial(handle_shutdown, bot, dashboard, loop, sig.name)
                )

        # Inicia bot e servidor em paralelo com tratamento de erros
        try:
            server_task = asyncio.create_task(server.serve())
            bot_task = asyncio.create_task(bot.start())
            
            # Aguarda as tasks com timeout
            await asyncio.wait(
                [server_task, bot_task],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=None
            )
            
            # Se alguma task falhou, cancela a outra
            if server_task.done() and server_task.exception():
                logger.error(f"Servidor web falhou: {server_task.exception()}")
                bot_task.cancel()
            elif bot_task.done() and bot_task.exception():
                logger.error(f"Bot falhou: {bot_task.exception()}")
                server_task.cancel()
                
        except asyncio.CancelledError:
            logger.info("Tasks canceladas, iniciando shutdown...")
        finally:
            # Garante que todas as tasks são canceladas
            for task in [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]:
                task.cancel()

    except KeyboardInterrupt:
        logger.info("Encerrando sistema por interrupção do usuário...")
    except Exception as e:
        logger.error(f"❌ Erro fatal: {str(e)}")
        logger.error(f"Detalhes: {traceback.format_exc()}")
    finally:
        # Sempre tenta limpar recursos
        try:
            await cleanup(bot, dashboard)
        except Exception as cleanup_error:
            logger.error(f"Erro durante cleanup: {cleanup_error}")
        sys.exit(1)

if __name__ == "__main__":
    # Configura evento loop do Windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Executa loop principal
    asyncio.run(main())
