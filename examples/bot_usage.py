"""
Exemplo de uso do BotCore em diferentes modos
"""
import asyncio
import logging
from datetime import datetime
from triangular_arbitrage.core.bot_core import BotCore
from triangular_arbitrage.config import TRADING_CONFIG

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def run_bot(test_mode: bool = True):
    """Executa o bot no modo especificado"""
    try:
        # Força modo de teste se especificado
        TRADING_CONFIG['test_mode'] = test_mode
        
        logger.info(f"Iniciando bot em modo {'TESTE' if test_mode else 'PRODUÇÃO'}")
        bot = BotCore()
        
        # Inicializa o bot
        if not await bot.initialize():
            logger.error("Falha ao inicializar o bot")
            return
            
        logger.info("Bot inicializado com sucesso")
        
        # Monitora oportunidades por um tempo
        start_time = datetime.now()
        duration = 300  # 5 minutos
        
        try:
            while (datetime.now() - start_time).total_seconds() < duration:
                if bot.opportunities:
                    logger.info("\nOportunidades detectadas:")
                    for opp in bot.opportunities[:3]:  # Mostra top 3
                        logger.info(
                            f"Rota: {opp['path']}\n"
                            f"Lucro: {opp['profit_percentage']:.2f}%\n"
                            f"Volume: {min(opp['volumes'].values()):.6f}\n"
                        )
                await asyncio.sleep(5)
                
        except KeyboardInterrupt:
            logger.info("Interrompido pelo usuário")
            
        finally:
            # Para o bot adequadamente
            await bot.stop()
            logger.info("Bot finalizado")
            
    except Exception as e:
        logger.error(f"Erro: {e}")

async def main():
    """Demonstra uso do bot em ambos os modos"""
    # Testa primeiro em modo de teste
    logger.info("\n=== Iniciando teste em MODO DE TESTE ===")
    await run_bot(test_mode=True)
    
    # Pergunta se quer executar em modo de produção
    response = input("\nDeseja executar em modo de produção? (s/N): ")
    if response.lower() == 's':
        logger.info("\n=== Iniciando em MODO DE PRODUÇÃO ===")
        logger.warning("ATENÇÃO: Operações reais serão executadas!")
        await run_bot(test_mode=False)
    else:
        logger.info("Modo de produção ignorado")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Programa finalizado pelo usuário")
    except Exception as e:
        logger.error(f"Erro fatal: {e}")