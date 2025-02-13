import asyncio
import sys
import os
from triangular_arbitrage.utils.logger import Logger
from triangular_arbitrage.core.bot_core import BotCore
from triangular_arbitrage.ui.web.app import WebDashboard
import uvicorn
import logging
from triangular_arbitrage.config import DB_CONFIG, DISPLAY_CONFIG
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Carrega variáveis de ambiente
load_dotenv()

async def init_components():
    """Inicializa os componentes do sistema de forma segura"""
    bot = None
    dashboard = None
    
    try:
        # Prepara configuração com credenciais do .env
        config = {
            'BINANCE_API_KEY': os.getenv('BINANCE_API_KEY', '').strip(),
            'BINANCE_API_SECRET': os.getenv('BINANCE_API_SECRET', '').strip(),
            'test_mode': os.getenv('TEST_MODE', 'true').lower() == 'true'
        }

        # Inicializa bot core com retry
        for attempt in range(3):  # 3 tentativas
            try:
                bot = BotCore(db=DB_CONFIG, display=DISPLAY_CONFIG, config=config)
                await bot.initialize()
                break
            except Exception as e:
                if attempt == 2:  # última tentativa
                    raise
                logger.error(f"Erro na tentativa {attempt + 1} de inicializar bot: {str(e)}")
                await asyncio.sleep(1)  # espera 1 segundo antes de tentar novamente

        # Inicializa web dashboard apenas se bot iniciou com sucesso
        if bot and bot.is_connected:
            dashboard = WebDashboard(bot)
            await dashboard.initialize()
            logger.info("✅ Componentes inicializados com sucesso")
        else:
            raise Exception("Bot não conectado após tentativas")

        return bot, dashboard
        
    except Exception as e:
        import traceback
        logger.error(f"❌ Erro fatal na inicialização: {str(e)}")
        logger.error(f"Detalhes: {traceback.format_exc()}")
        
        # Tenta limpar recursos se algo foi criado
        if bot:
            await bot.cleanup()
        if dashboard:
            await dashboard.cleanup()
            
        raise

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

        # Configura servidor web com timeouts adequados
        config = uvicorn.Config(
            app=dashboard.app,
            host="127.0.0.1",
            port=8000,
            log_level="info",
            reload=False,
            workers=1,
            timeout_keep_alive=30,
            loop="auto"
        )
        server = uvicorn.Server(config)

        # Inicia bot e servidor em paralelo
        await asyncio.gather(
            server.serve(),
            bot.start(),
            return_exceptions=True
        )

    except KeyboardInterrupt:
        logger.info("Encerrando sistema...")
    except Exception as e:
        import traceback
        logger.error(f"❌ Erro fatal: {str(e)}")
        logger.error(f"Detalhes: {traceback.format_exc()}")
        sys.exit(1)
    finally:
        # Garante que recursos são liberados
        try:
            if bot:
                await bot.stop()
            if dashboard:
                await dashboard.cleanup()
            logger.info("✅ Sistema encerrado com sucesso")
        except Exception as cleanup_error:
            logger.error(f"Erro ao limpar recursos: {str(cleanup_error)}")

if __name__ == "__main__":
    # Configura evento loop do Windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Executa loop principal
    asyncio.run(main())
