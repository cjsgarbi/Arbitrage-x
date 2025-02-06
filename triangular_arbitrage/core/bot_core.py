from typing import Dict, List, Optional
import asyncio
from datetime import datetime
from .currency_core import CurrencyCore
from ..utils.logger import Logger
from ..utils.db_helpers import DBHelpers
from ..utils.pair_ranker import PairRanker
from ..ui.display import Display
from ..config import BINANCE_CONFIG, TRADING_CONFIG
from decimal import Decimal
import aiohttp
from binance import AsyncClient
import zmq.asyncio
import logging
import time


class BotCore:
    def __init__(self, config, display=None):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.display = display
        self.running = False
        self.currency_core = None
        self.exchange = None  # Será inicializado no start()

        # Configuração inicial
        self.logger.info("🔄 Iniciando BotCore...")
        if self.config.get('SIMULATION_MODE'):
            self.logger.info("⚠️ Modo simulação ativado")

        # Componentes principais
        self.db_helpers = DBHelpers()
        self.pair_ranker = PairRanker()

        # Estado do bot
        self.storage = {
            'streams': {},
            'candidates': [],
            'pair_ranks': {},
            'trading': {
                'queue': [],
                'demo_balance': TRADING_CONFIG['demo_balance'].copy()
            }
        }

        # Configurações de arbitragem
        self.arbitrage_config = {
            'start': 'BTC',
            'paths': ['ETH', 'BNB', 'USDT']
        }

    async def initialize_exchange(self):
        """Inicializa conexão com a exchange"""
        try:
            self.logger.info("🔄 Conectando à Binance...")

            # Configuração específica para Testnet com recvWindow aumentado
            self.exchange = AsyncClient(
                api_key=self.config['BINANCE_API_KEY'],
                api_secret=self.config['BINANCE_API_SECRET'],
                testnet=True,  # Força uso da Testnet
                tld='com',     # Importante para Testnet
                recv_window=60000  # Aumenta a janela de tempo para 60 segundos
            )

            self.logger.info("✅ Conectado à Binance")

            # Sincroniza o timestamp do servidor
            server_time = await self.exchange.get_server_time()
            time_offset = int(
                server_time['serverTime']) - int(time.time() * 1000)
            self.logger.info(
                f"⏰ Diferença de tempo com servidor: {time_offset}ms")

            # Testa a conexão obtendo o saldo da conta
            account = await self.exchange.get_account()
            if account:
                self.logger.info("✅ Conexão testada com sucesso")
                balances = {asset['asset']: float(asset['free'])
                            for asset in account['balances']
                            if float(asset['free']) > 0}
                self.logger.info(f"💰 Saldos disponíveis: {balances}")

            return True

        except Exception as e:
            self.logger.error(f"❌ Erro ao conectar com Binance: {str(e)}")
            raise e

    async def start(self):
        """Inicia o bot"""
        try:
            self.logger.info("🚀 Iniciando bot...")
            self.logger.info("🔄 Conectando à exchange...")

            if not self.config.get('SIMULATION_MODE'):
                # Modo real - requer conexão com Binance
                self.logger.info("🔄 Conectando à Binance...")
                await self.initialize_exchange()
                self.logger.info("✅ Conexão estabelecida com sucesso")
            else:
                # Modo simulação - não requer conexão
                self.logger.info(
                    "⚠️ Modo simulação ativado - Usando dados simulados")
                self.exchange = None

            # Inicializa CurrencyCore
            self.logger.info("🔄 Iniciando CurrencyCore...")
            self.currency_core = CurrencyCore(self.exchange, self.config)

            if not self.config.get('SIMULATION_MODE'):
                # Inicializa apenas se não estiver em modo simulação
                await self.currency_core.initialize()

            # Inicia monitoramento
            self.running = True

            # Em modo simulação, apenas atualiza o display
            if self.config.get('SIMULATION_MODE'):
                while self.running:
                    if self.display:
                        await self.display.update_arbitrage_opportunities([])
                    await asyncio.sleep(1)
            else:
                # Modo normal - inicia stream de tickers
                await self.currency_core.start_ticker_stream()

        except Exception as e:
            self.logger.error(f"❌ Erro ao iniciar bot: {str(e)}")
            if self.config.get('DEBUG', False):
                self.logger.error(f"🔍 Detalhes: {str(e.__class__.__name__)}")
            raise

    async def stop(self):
        """Para o bot graciosamente"""
        self.running = False

        try:
            # Fecha currency core
            if hasattr(self, 'currency_core'):
                await self.currency_core.close()

            # Fecha cliente Binance
            if hasattr(self, 'exchange'):
                await self.exchange.close_connection()

            # Fecha sessão HTTP
            if hasattr(self, 'session'):
                if not self.session.closed:
                    await self.session.close()

            # Aguarda tasks pendentes
            tasks = [t for t in asyncio.all_tasks()
                     if t is not asyncio.current_task()]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

            self.logger.info("Bot encerrado com sucesso")

        except Exception as e:
            self.logger.error(f"Erro ao encerrar bot: {e}")

    async def get_demo_balance(self, asset: str) -> Decimal:
        """Retorna saldo demo de um ativo"""
        return Decimal(self.storage['trading']['demo_balance'].get(asset, '0'))

    async def update_demo_balance(self, asset: str, amount: Decimal):
        """Atualiza saldo demo de um ativo"""
        current = await self.get_demo_balance(asset)
        self.storage['trading']['demo_balance'][asset] = str(current + amount)

    async def send_to_executor(self, opportunity: Dict):
        """Envia oportunidade para o executor Ruby via ZMQ"""
        try:
            # Configura socket ZMQ
            context = zmq.asyncio.Context()
            socket = context.socket(zmq.PUB)
            socket.bind("tcp://*:5555")

            # Prepara mensagem
            message = {
                'type': 'opportunity',
                'data': opportunity,
                'timestamp': datetime.now().isoformat()
            }

            # Envia para o executor
            await socket.send_json(message)
            self.logger.info(
                f"Oportunidade enviada para executor: {opportunity['profit']:.2f}%")

        except Exception as e:
            self.logger.error(f"Erro ao enviar para executor: {e}")

    async def on_ticker_update(self, stream: Dict):
        """Callback para atualização de tickers"""
        try:
            # Atualiza stream no storage
            stream_id = 'allMarketTickers'
            self.storage['streams'][stream_id] = stream

            # Busca oportunidades de arbitragem
            candidates = self.currency_core.get_dynamic_candidates_from_stream(
                stream['obj'],
                self.arbitrage_config
            )

            # Prepara dados para display
            display_data = []
            viable_opportunities = 0
            total_opportunities = len(candidates) if candidates else 0

            if candidates:
                self.storage['candidates'] = candidates
                self.logger.debug(
                    f"🔍 Analisando {len(candidates)} oportunidades potenciais")

                # Processa cada oportunidade
                for c in candidates:
                    try:
                        # Calcula volumes
                        volumes = [
                            float(c['a_volume']),
                            float(c['b_volume']),
                            float(c['c_volume'])
                        ]
                        volume = min(volumes)
                        avg_volume = sum(volumes) / 3

                        # Calcula spread médio
                        spreads = [
                            abs(float(c['a_bid']) -
                                float(c['a_ask'])) / float(c['a_ask']),
                            abs(float(c['b_bid']) -
                                float(c['b_ask'])) / float(c['b_ask']),
                            abs(float(c['c_bid']) -
                                float(c['c_ask'])) / float(c['c_ask'])
                        ]
                        avg_spread = sum(spreads) / 3 * 100  # em porcentagem

                        # Calcula lucro em porcentagem
                        profit = (float(c['rate']) - 1) * 100

                        # Calcula score da oportunidade (0-100)
                        volume_score = min(volume / 1.0, 1.0) * \
                            40  # Volume até 1 BTC
                        profit_score = min(
                            profit / 2.0, 1.0) * 40  # Lucro até 2%
                        spread_score = (
                            1 - min(avg_spread / 1.0, 1.0)) * 20  # Spread até 1%
                        opportunity_score = volume_score + profit_score + spread_score

                        # Só adiciona se o lucro for viável
                        if profit > 0.2:  # Reduzido para 0.2%
                            viable_opportunities += 1
                            opp = {
                                'a_step_from': c['a_step_from'],
                                'a_step_to': c['a_step_to'],
                                'b_step_from': c['b_step_from'],
                                'b_step_to': c['b_step_to'],
                                'c_step_from': c['c_step_from'],
                                'c_step_to': c['c_step_to'],
                                'rate': float(c['rate']),
                                'profit': profit,
                                'volume': volume,
                                'avg_volume': avg_volume,
                                'avg_spread': avg_spread,
                                'score': opportunity_score,
                                'timestamp': datetime.now().isoformat()
                            }
                            display_data.append(opp)

                            # Log detalhado para oportunidades promissoras
                            if profit > 0.5:
                                self.logger.info(
                                    f"💰 Oportunidade encontrada:\n"
                                    f"   Rota: {opp['a_step_from']}->{opp['b_step_from']}->{opp['c_step_from']}\n"
                                    f"   Lucro: {profit:.2f}%\n"
                                    f"   Volume: {volume:.4f} BTC\n"
                                    f"   Spread Médio: {avg_spread:.2f}%\n"
                                    f"   Score: {opportunity_score:.1f}/100"
                                )

                    except Exception as e:
                        self.logger.error(
                            f"❌ Erro ao processar candidato: {e}")
                        continue

                if display_data:
                    self.logger.info(
                        f"✨ Encontradas {viable_opportunities} oportunidades viáveis de {total_opportunities} analisadas")

                    # Ordena por score e envia melhores oportunidades
                    sorted_opps = sorted(
                        display_data,
                        key=lambda x: x['score'],
                        reverse=True
                    )

                    # Envia top 3 para executor
                    for opp in sorted_opps[:3]:
                        if opp['profit'] > 0.5 and opp['score'] > 60:
                            await self.send_to_executor(opp)
                            self.logger.info(
                                f"📤 Enviada para executor: {opp['profit']:.2f}% (Score: {opp['score']:.1f})")

            # Atualiza UI com todas oportunidades encontradas
            await self.display.update_arbitrage_opportunities(display_data)

            # Salva dados se configurado
            if self.config.get('SAVE_DATA', False):
                await self.db_helpers.save_arb_rows(
                    candidates,
                    self.storage.get('db'),
                    self.logger
                )

        except Exception as e:
            self.logger.error(f"❌ Erro ao processar ticker: {e}")
            if self.config.get('DEBUG', False):
                self.logger.error(f"Detalhes: {str(e)}", exc_info=True)

    def get_storage(self) -> Dict:
        """Retorna estado atual do storage"""
        return self.storage

    def get_config(self) -> Dict:
        """Retorna configurações atuais"""
        return self.config
