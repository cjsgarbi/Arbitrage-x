import asyncio
import logging
from triangular_arbitrage.core.bot_core import BotCore
from triangular_arbitrage.config import BINANCE_CONFIG

# Configura logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_ai_pair_selection():
    try:
        # Inicializa o bot com configurações de teste
        config = {
            'BINANCE_API_KEY': BINANCE_CONFIG.get('api_key'),
            'BINANCE_API_SECRET': BINANCE_CONFIG.get('api_secret'),
            'test_mode': True
        }
        
        bot = BotCore(config=config)
        
        # Inicializa conexão
        await bot.initialize()
        
        logger.info("Testando seleção de pares com IA...")
        
        # Tenta carregar pares usando IA
        pairs = await bot._load_top_pairs()
        
        logger.info(f"Pares selecionados pela IA: {pairs}")
        logger.info(f"Total de pares: {len(pairs)}")
        
        # Verifica se retornou pares válidos
        assert pairs, "Nenhum par retornado"
        assert isinstance(pairs, list), "Resultado deve ser uma lista"
        assert all(isinstance(p, str) for p in pairs), "Todos os pares devem ser strings"
        
        logger.info("✅ Teste concluído com sucesso!")
        
    except Exception as e:
        logger.error(f"❌ Erro no teste: {e}")
        raise
    finally:
        if bot:
            await bot._cleanup()

if __name__ == "__main__":
    asyncio.run(test_ai_pair_selection())
