import asyncio
import logging
import time
from datetime import datetime
from triangular_arbitrage.core.bot_core import BotCore

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WebSocketStabilityTest:
    def __init__(self):
        self.bot = None
        self.start_time = None
        self.metrics = {
            'reconnections': 0,
            'messages_processed': 0,
            'buffer_overflow_count': 0,
            'max_latency': 0,
            'avg_latency': 0,
            'latency_samples': []
        }
        self.test_duration = 300  # 5 minutos de teste

    async def monitor_metrics(self):
        """Monitora métricas de performance em tempo real"""
        while True:
            try:
                if self.bot and self.bot.last_latency:
                    self.metrics['latency_samples'].append(self.bot.last_latency)
                    self.metrics['max_latency'] = max(self.metrics['max_latency'], self.bot.last_latency)
                    self.metrics['avg_latency'] = sum(self.metrics['latency_samples']) / len(self.metrics['latency_samples'])

                # Registra métricas atuais
                logger.info(
                    f"Métricas:\n"
                    f"- Reconexões: {self.metrics['reconnections']}\n"
                    f"- Mensagens processadas: {self.metrics['messages_processed']}\n"
                    f"- Buffer overflow: {self.metrics['buffer_overflow_count']}\n"
                    f"- Latência máxima: {self.metrics['max_latency']:.2f}ms\n"
                    f"- Latência média: {self.metrics['avg_latency']:.2f}ms"
                )

                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Erro no monitoramento: {e}")
                await asyncio.sleep(1)

    async def run_test(self):
        """Executa o teste de estabilidade"""
        try:
            logger.info("Iniciando teste de estabilidade do WebSocket...")
            self.start_time = time.time()

            # Inicializa o bot com configuração de teste
            self.bot = BotCore(
                config={
                    'test_mode': True,
                    'BINANCE_API_KEY': 'sua_api_key',
                    'BINANCE_API_SECRET': 'seu_api_secret'
                }
            )

            # Inicia monitoramento em background
            monitor_task = asyncio.create_task(self.monitor_metrics())

            # Executa o bot pelo período de teste
            await asyncio.gather(
                self.bot.initialize(),
                self._run_test_duration(),
                return_exceptions=True
            )

            # Cancela monitoramento
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

            # Gera relatório final
            await self._generate_report()

        except Exception as e:
            logger.error(f"Erro durante o teste: {e}")
            raise
        finally:
            if self.bot:
                await self.bot.cleanup()

    async def _run_test_duration(self):
        """Executa o teste pelo tempo especificado"""
        try:
            await asyncio.sleep(self.test_duration)
        finally:
            if self.bot:
                await self.bot.stop()

    async def _generate_report(self):
        """Gera relatório detalhado do teste"""
        test_duration = time.time() - self.start_time
        messages_per_second = self.metrics['messages_processed'] / test_duration

        report = f"""
=== Relatório de Teste de Estabilidade WebSocket ===
Duração do teste: {test_duration:.2f} segundos
Mensagens processadas: {self.metrics['messages_processed']}
Taxa de mensagens: {messages_per_second:.2f}/s
Reconexões: {self.metrics['reconnections']}
Buffer overflows: {self.metrics['buffer_overflow_count']}

Latência:
- Máxima: {self.metrics['max_latency']:.2f}ms
- Média: {self.metrics['avg_latency']:.2f}ms

Status final: {'✅ Estável' if self.metrics['reconnections'] < 5 and self.metrics['avg_latency'] < 500 else '❌ Instável'}
        """

        logger.info(report)
        
        # Salva relatório em arquivo
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        with open(f'websocket_stability_test_{timestamp}.log', 'w') as f:
            f.write(report)

async def main():
    test = WebSocketStabilityTest()
    await test.run_test()

if __name__ == '__main__':
    asyncio.run(main())