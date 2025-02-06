import asyncio
import argparse
import logging
import os
import signal
import sys
from pathlib import Path
from dotenv import load_dotenv

from triangular_arbitrage.core.bot_core import BotCore
from triangular_arbitrage.utils.logger import Logger
from triangular_arbitrage.utils.db_helpers import DBHelpers
from triangular_arbitrage.ui.display import Display

# Carrega variáveis de ambiente
load_dotenv()


def setup_logging():
    """Configura sistema de logs"""
    logger = Logger()
    return logger


def parse_args():
    """Processa argumentos da linha de comando"""
    parser = argparse.ArgumentParser(
        description='Bot de Arbitragem Triangular')
    parser.add_argument('--simulation', action='store_true',
                        help='Executa em modo simulação')
    parser.add_argument('--debug', action='store_true',
                        help='Ativa logs de debug')
    return parser.parse_args()


async def shutdown(bot, signal=None):
    """Encerra o bot graciosamente"""
    if signal:
        logging.info(f"Recebido sinal de encerramento {signal}...")

    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]

    logging.info(f"Cancelando {len(tasks)} tarefas pendentes")
    await asyncio.gather(*tasks, return_exceptions=True)

    await bot.stop()
    asyncio.get_event_loop().stop()


def handle_exception(loop, context):
    msg = context.get("exception", context["message"])
    logging.error(f"Erro no loop de eventos: {msg}")


async def main():
    """Função principal do bot"""
    # Processa argumentos
    args = parse_args()

    # Configura logs
    logger = setup_logging()
    if args.debug:
        logger.logger.setLevel(logging.DEBUG)

    try:
        # Banner inicial
        print("\n" + "="*50)
        print("🤖 Bot de Arbitragem Triangular")
        print("="*50 + "\n")

        # Prepara configuração
        config = {
            'BINANCE_API_KEY': os.getenv('BINANCE_API_KEY', '').strip().replace('"', ''),
            'BINANCE_API_SECRET': os.getenv('BINANCE_API_SECRET', '').strip().replace('"', ''),
            'SIMULATION_MODE': args.simulation,
            'SAVE_DATA': os.getenv('SAVE_DATA', 'false').lower() == 'true',
            'DEBUG': args.debug,
            'TEST_MODE': True  # Força modo de teste
        }

        if not config['BINANCE_API_KEY'] or not config['BINANCE_API_SECRET']:
            raise ValueError(
                "❌ API Key e Secret da Binance Testnet não encontrados no arquivo .env")

        # Configura loop de eventos
        loop = asyncio.get_event_loop()
        loop.set_exception_handler(handle_exception)

        # Inicializa componentes
        logger.logger.info("🔄 Inicializando componentes do bot...")

        # Inicializa display
        display = Display()
        logger.logger.info("✅ Display inicializado")

        # Inicializa banco de dados
        db = DBHelpers()
        await db.setup()
        logger.logger.info("✅ Banco de dados inicializado")

        # Inicializa bot
        bot = BotCore(config=config, display=display)
        logger.logger.info("✅ Bot core inicializado")

        # Configura sinais para encerramento gracioso
        if os.name == 'nt':  # Windows
            signal.signal(signal.SIGINT, lambda s,
                          f: asyncio.create_task(shutdown(bot)))
            signal.signal(signal.SIGTERM, lambda s,
                          f: asyncio.create_task(shutdown(bot)))
        else:  # Unix/Linux
            loop.add_signal_handler(
                signal.SIGINT, lambda: asyncio.create_task(shutdown(bot)))
            loop.add_signal_handler(
                signal.SIGTERM, lambda: asyncio.create_task(shutdown(bot)))

        # Aviso modo simulação
        if config['SIMULATION_MODE']:
            logger.logger.warning(
                "⚠️  MODO SIMULAÇÃO ATIVO - Nenhuma ordem será enviada")
            print("\n⚠️  MODO SIMULAÇÃO - Apenas monitorando oportunidades\n")
            print("📊 Iniciando monitoramento de mercado...")
            print("⌛ Aguarde enquanto coletamos dados iniciais...\n")

        # Inicia bot
        try:
            await bot.start()
        except Exception as e:
            logger.logger.error(f"❌ Erro fatal: {str(e)}")
            print(f"\n❌ Erro: {str(e)}")
            print("🔄 Tentando reiniciar o bot em 5 segundos...")
            await asyncio.sleep(5)
            await shutdown(bot)

    except Exception as e:
        logger.logger.error(f"❌ Erro fatal: {str(e)}")
        if config.get('DEBUG', False):
            logger.logger.error(f"🔍 Detalhes: {str(e.__class__.__name__)}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot encerrado pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro fatal: {str(e)}")
