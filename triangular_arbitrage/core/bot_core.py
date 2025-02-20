"""
Núcleo do bot de arbitragem
"""
from typing import Optional, Dict, List
import logging
import asyncio
import time
import json
import os
from datetime import datetime
from decimal import Decimal

from ..config import (
    BINANCE_CONFIG, 
    TRADING_CONFIG, 
    DB_CONFIG, 
    AI_CONFIG
)
from .connection_manager import ConnectionManager
from .currency_core import CurrencyCore
from .events_core import EventsCore
from .ai_pair_finder import AIPairFinder
from .ai.arbitrage_analyzer import ArbitrageAnalyzer
from ..utils.backup_manager import BackupManager
from ..utils.logger import Logger

logger = logging.getLogger(__name__)

class BotCore:
    def __init__(self, config: Optional[Dict] = None):
        """Inicializa o bot"""
        self.logger = logging.getLogger(__name__)
        
        # Configura chaves da API
        self.config = config or {}
        api_key = self.config.get('BINANCE_API_KEY', BINANCE_CONFIG['API_KEY'])
        api_secret = self.config.get('BINANCE_API_SECRET', BINANCE_CONFIG['API_SECRET'])
        
        # Cria diretórios necessários
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data')
        self.backup_dir = os.path.join(self.data_dir, 'backups')
        self.config_dir = os.path.join(self.backup_dir, 'config')
        self.logs_dir = os.path.join(self.backup_dir, 'logs')
        
        for directory in [self.data_dir, self.backup_dir, self.config_dir, self.logs_dir]:
            os.makedirs(directory, exist_ok=True)

        # Estado do bot
        self.test_mode = TRADING_CONFIG['test_mode']
        self.running = True
        self.opportunities = []
        self.trades = []
        self.start_time = datetime.now()
        self.last_update = None
        
        # Gerenciador de conexões
        self.connection = ConnectionManager(
            api_key=api_key,
            api_secret=api_secret
        )
        
        # Componentes principais
        self.currency_core = CurrencyCore(
            exchange=None,  # Será atualizado após conexão
            config={'test_mode': self.test_mode}
        )
        
        self.events_core = EventsCore()
        
        self.backup_manager = BackupManager(
            db_path=DB_CONFIG['DB_FILE'],
            backup_dir=DB_CONFIG['BACKUP_DIR'],
            config_dir=self.config_dir,
            logs_dir=self.logs_dir
        )

        try:
            # Inicializa interface de monitoramento
            from ..ui.display import Display
            self.display = Display()
            
            if not hasattr(self, 'display') or not self.display:
                raise ValueError("Display não foi inicializado corretamente")
                
            # Verifica se display está pronto
            if not hasattr(self.display, 'table') or not self.display.table:
                raise ValueError("Tabela do display não foi configurada")
                
            self.logger.info("📊 Interface de monitoramento iniciada com sucesso")
                
        except ImportError as e:
            self.logger.error(f"❌ Erro ao importar módulo display: {e}")
            raise
        except Exception as e:
            self.logger.error(f"❌ Erro ao inicializar display: {e}")
            raise
        
        # Componentes de IA
        self.ai_pair_finder = AIPairFinder()
        self.arbitrage_analyzer = ArbitrageAnalyzer()
        
        # Cache e controles
        self._price_cache_lock = asyncio.Lock()
        self.price_cache = {}
        self.symbol_pairs = set()
        self.last_process_time = time.time()

        # Histórico
        self.opportunities_history = []
        self.max_history_size = 1000
        self.history_file = os.path.join(self.data_dir, 'opportunities_history.json')
        self._load_history()

    def _load_history(self):
        """Carrega histórico de oportunidades"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    self.opportunities_history = json.load(f)
        except Exception as e:
            self.logger.error(f"Erro ao carregar histórico: {e}")
            self.opportunities_history = []

    @property
    def is_connected(self) -> bool:
        """Retorna estado de conexão do bot"""
        return self.connection.is_connected if self.connection else False

    async def initialize(self) -> bool:
        """Inicializa o bot"""
        try:
            # Conecta à Binance
            if not await self.connection.connect():
                raise ValueError("Falha na conexão com a Binance")
            
            # Atualiza exchange no currency_core
            self.currency_core.exchange = self.connection.client

            self.logger.info("✅ Bot inicializado com sucesso")
            
            if self.test_mode:
                self.logger.info("🔬 Modo de teste ativo - monitorando oportunidades reais")
                self.logger.info(f"Profit mínimo para teste: {AI_CONFIG['test_mode']['min_profit']}%")
            else:
                self.logger.warning("⚠️ Modo de produção ativo - executando operações reais!")
                self.logger.info(f"Profit mínimo para produção: {AI_CONFIG['prod_mode']['min_profit']}%")

            return True

        except Exception as e:
            self.logger.error(f"❌ Erro na inicialização: {e}")
            return False

    async def start(self):
        """Inicia o bot"""
        try:
            # Carrega pares iniciais
            initial_pairs = await self.ai_pair_finder.get_potential_pairs(self.display)
            if not initial_pairs:
                raise ValueError("Nenhum par retornado pelo AI Pair Finder")
            
            self.symbol_pairs.update(initial_pairs)
            
            # Inicia stream de mercado
            if not await self.connection.start_market_stream(initial_pairs):
                raise ValueError("Falha ao iniciar stream de mercado")
            
            # Processa mensagens do stream
            await self.connection.process_socket_messages(self._handle_market_data)
            
        except Exception as e:
            self.logger.error(f"Erro ao iniciar bot: {e}")
        finally:
            await self.stop()

    async def stop(self):
        """Para o bot"""
        self.running = False
        await self._cleanup()
        self.logger.info("Bot finalizado")

    async def _handle_market_data(self, msg: Dict):
        """Processa dados do mercado"""
        try:
            if not msg or 'data' not in msg:
                return
                
            data = msg['data']
            if data['e'] != 'bookTicker':
                return
                
            # Atualiza cache de preços
            symbol = data['s']
            price_data = {
                'bid': float(data['b']),
                'ask': float(data['a']),
                'bid_qty': float(data['B']),
                'ask_qty': float(data['A']),
                'timestamp': time.time()
            }
            
            async with self._price_cache_lock:
                self.price_cache[symbol] = price_data

            # Detecta oportunidades periodicamente
            current_time = time.time()
            if current_time - self.last_process_time >= 0.1:  # 100ms
                await self._detect_opportunities()
                self.last_process_time = current_time

        except Exception as e:
            self.logger.error(f"Erro no processamento de dados: {e}")

    def _validate_opportunity_data(self, opportunity: Dict, analysis: Dict) -> Optional[Dict]:
        """Valida e formata dados da oportunidade"""
        try:
            # Valida dados obrigatórios
            if not all(k in opportunity for k in ['path', 'profit_percentage', 'volumes']):
                self.logger.warning("Dados obrigatórios faltando na oportunidade")
                return None
            
            # Formata dados
            formatted_data = {
                'path': opportunity['path'],
                'profit': float(opportunity['profit_percentage']),
                'market_metrics': {
                    'volumes': opportunity['volumes'],
                    'spread': opportunity.get('spread', 0),
                    'execution_time': analysis.get('execution_time', 0),
                    'liquidity': sum(opportunity['volumes'].values()),
                    'risk_score': analysis.get('risk_score', 0),
                    'volatility': analysis.get('volatility', 0),
                    'confidence_score': analysis.get('confidence_score', 0),
                    'slippage': analysis.get('slippage', 0)
                },
                'timestamp': datetime.now().isoformat()
            }
            
            # Valida tipos e ranges
            if not (isinstance(formatted_data['profit'], float) and formatted_data['profit'] >= 0):
                self.logger.warning("Profit inválido")
                return None
                
            if not formatted_data['market_metrics']['volumes']:
                self.logger.warning("Volumes vazios")
                return None
                
            return formatted_data
            
        except Exception as e:
            self.logger.error(f"Erro ao validar dados: {e}")
            return None

    async def _detect_opportunities(self):
        """Detecta oportunidades de arbitragem"""
        try:
            # Copia cache para processamento
            async with self._price_cache_lock:
                prices = self.price_cache.copy()

            opportunities = []
            bases = ['BTC', 'ETH', 'USDT', 'BNB']
            
            for base in bases:
                pairs = [p for p in prices.keys() if base in p]
                for pair_a in pairs:
                    for pair_b in pairs:
                        if pair_a != pair_b:
                            opp = self._check_arbitrage(pair_a, pair_b, base, prices)
                            if opp:
                                # Analisa oportunidade
                                analysis = await self.arbitrage_analyzer.analyze_opportunity(opp)
                                if analysis and analysis.get('confidence_score', 0) >= AI_CONFIG['min_confidence']:
                                    # Valida e formata dados mantendo todas as métricas
                                    opportunity_data = {
                                        **opp,
                                        'analysis': analysis,
                                        'market_metrics': {
                                            'volumes': opp['volumes'],
                                            'spread': opp.get('spread', 0),
                                            'execution_time': analysis.get('execution_time', 0),
                                            'liquidity': sum(opp['volumes'].values()),
                                            'risk_score': analysis.get('risk_score', 0),
                                            'volatility': analysis.get('volatility', 0),
                                            'confidence_score': analysis.get('confidence_score', 0),
                                            'slippage': analysis.get('slippage', 0)
                                        }
                                    }
                                    
                                    # Valida estrutura dos dados
                                    validated_data = self._validate_opportunity_data(opportunity_data, analysis)
                                    if not validated_data:
                                        continue
                                    opportunities.append(opportunity_data)
                                    
                                    # Atualiza display com dados em tempo real
                                    await self.display.update_opportunities([opportunity_data])

            # Processa e exibe oportunidades
            if opportunities:
                # Ordena por lucro
                opportunities.sort(key=lambda x: float(x['profit_percentage']), reverse=True)
                self.opportunities = opportunities[:10]  # Mantém top 10
                self.last_update = datetime.now()
                
                # Atualiza display
                await self.display.update_opportunities([
                    {
                        'path': opp['path'],
                        'profit': opp['profit_percentage'],
                        'market_metrics': {
                            'volumes': opp['volumes'],
                            'slippage': 0.001,  # 0.1% estimado
                            'execution_time': 0.5,  # 500ms estimado
                            'liquidity': sum(opp['volumes'].values()),
                            'risk_score': 5,  # Score médio
                            'spread': sum(v/k for k,v in opp['volumes'].items())/len(opp['volumes']),
                            'volatility': 0.5,  # Volatilidade média
                            'confidence_score': 80  # Confiança base
                        }
                    }
                    for opp in opportunities[:10]
                ])

                # Executa/simula melhores oportunidades
                for opp in opportunities[:3]:  # Processa top 3
                    await self._execute_opportunity(opp)

        except Exception as e:
            self.logger.error(f"Erro na detecção de oportunidades: {e}")

    def _check_arbitrage(self, pair_a: str, pair_b: str, base: str, prices: Dict) -> Optional[Dict]:
        """Verifica potencial de arbitragem"""
        try:
            # Extrai símbolos
            symbol_a = pair_a.replace(base, '')
            symbol_b = pair_b.replace(base, '')
            pair_c = f"{symbol_a}{symbol_b}"

            if pair_c not in prices:
                return None

            # Calcula taxas
            fee = Decimal('0.001')  # 0.1%
            
            # Calcula preços considerando taxas
            price_a = Decimal(str(prices[pair_a]['ask'])) * (1 + fee)
            price_b = Decimal(str(prices[pair_b]['bid'])) * (1 - fee)
            price_c = Decimal(str(prices[pair_c]['bid'])) * (1 - fee)

            # Calcula lucro potencial
            profit = (price_b * price_c / price_a - 1) * 100

            if profit > 0:
                return {
                    'path': f"{base}->{symbol_a}->{symbol_b}->{base}",
                    'pairs': [pair_a, pair_b, pair_c],
                    'profit_percentage': float(profit),
                    'timestamp': datetime.now().isoformat(),
                    'prices': {
                        pair_a: float(price_a),
                        pair_b: float(price_b),
                        pair_c: float(price_c)
                    },
                    'volumes': {
                        pair_a: float(prices[pair_a]['ask_qty']),
                        pair_b: float(prices[pair_b]['bid_qty']),
                        pair_c: float(prices[pair_c]['bid_qty'])
                    }
                }

            return None

        except Exception as e:
            self.logger.error(f"Erro ao verificar arbitragem: {e}")
            return None

    async def _execute_opportunity(self, opportunity: Dict):
        """Executa oportunidade de arbitragem"""
        try:
            if self.test_mode:
                # Monitora oportunidade real
                self.logger.info(f"Monitorando oportunidade real: {opportunity['path']} (Profit: {opportunity['profit_percentage']:.2f}%)")
                result = {
                    'success': True,
                    'profit': opportunity['profit_percentage'],
                    'monitored': True
                }
            else:
                # Executa operação real
                self.logger.warning(f"Executando: {opportunity['path']} (Profit: {opportunity['profit_percentage']:.2f}%)")
                result = await self.connection.execute_trades([
                    {
                        'symbol': pair,
                        'side': 'BUY',
                        'type': 'MARKET',
                        'quantity': vol
                    }
                    for pair, vol in zip(opportunity['pairs'], opportunity['volumes'])
                ])

            # Formata dados de execução
            execution_data = {
                **opportunity,
                'result': result,
                'executed_at': datetime.now().isoformat(),
                'market_metrics': opportunity.get('market_metrics', {})
            }

            # Atualiza histórico e display
            if len(self.opportunities_history) >= self.max_history_size:
                self.opportunities_history.pop(0)
            self.opportunities_history.append(execution_data)
            
            # Atualiza display em tempo real
            await self.display.update_opportunities([execution_data])

        except Exception as e:
            self.logger.error(f"Erro ao executar oportunidade: {e}")

    async def _cleanup(self):
        """Limpa recursos"""
        try:
            # Finaliza display
            if hasattr(self, 'display'):
                self.display.stop()
                self.logger.info("📊 Display finalizado")

            # Desconecta da Binance
            await self.connection.disconnect()
            
            # Fecha currency core
            if self.currency_core:
                await self.currency_core.close()
            
            # Salva histórico
            if self.opportunities_history:
                self.logger.info("💾 Salvando histórico...")
                with open(self.history_file, 'w') as f:
                    json.dump(self.opportunities_history, f, indent=2)
                self.logger.info("✅ Histórico salvo com sucesso")
                
        except Exception as e:
            self.logger.error(f"❌ Erro na limpeza: {e}")
