from typing import Dict, List, Optional, Union
from decimal import Decimal
import asyncio
from datetime import datetime
import logging

from binance.client import Client, AsyncClient
from binance.exceptions import BinanceAPIException
from ..config import TRADING_CONFIG

logger = logging.getLogger(__name__)


class TradingCore:
    def __init__(self, client: Union[Client, AsyncClient]):
        """Inicializa o TradingCore

        Args:
            client: Cliente Binance (síncrono ou assíncrono)
        """
        self.client = client
        self.min_profit = Decimal(str(TRADING_CONFIG.get('min_profit', '0.2')))
        self.trade_amount = Decimal(str(TRADING_CONFIG.get('min_volume_btc', '0.01')))
        self.max_slippage = Decimal(str(TRADING_CONFIG.get('max_slippage', '0.002')))
        self.fee_rate = Decimal(str(TRADING_CONFIG.get('fee_rate', '0.001')))
        
        # Modos de operação
        self.test_mode = TRADING_CONFIG.get('test_mode', True)
        self.simulation_mode = TRADING_CONFIG.get('SIMULATION_MODE', False)
        
        # Controle de trades
        self.active_trades: List[Dict] = []
        self.completed_trades: List[Dict] = []
        
        # Stop loss e take profit
        self.stop_loss_pct = Decimal('0.01')  # 1% de perda máxima
        self.take_profit_pct = Decimal('0.005')  # 0.5% de lucro garantido
        
        if self.test_mode:
            logger.info("🔬 TradingCore iniciado em modo de teste (ordens não serão executadas)")
        elif self.simulation_mode:
            logger.info("🎮 TradingCore iniciado em modo de simulação")
        else:
            logger.warning("⚠️ TradingCore iniciado em modo de execução real!")
            
        logger.info(f"Configurações:"
                   f"\n   Min Profit: {self.min_profit}%"
                   f"\n   Trade Amount: {self.trade_amount} BTC"
                   f"\n   Max Slippage: {self.max_slippage}%"
                   f"\n   Fee Rate: {self.fee_rate}%")

    async def check_balance(self, asset: str, required_amount: Decimal) -> bool:
        """Verifica se há saldo suficiente para uma operação

        Args:
            asset: Símbolo do ativo (ex: BTC)
            required_amount: Quantidade necessária

        Returns:
            bool: True se há saldo suficiente
        """
        try:
            balance = await self.get_balance(asset)
            if balance < required_amount:
                logger.warning(
                    f"⚠️ Saldo insuficiente de {asset}. "
                    f"Necessário: {required_amount}, Disponível: {balance}"
                )
                return False
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao verificar saldo de {asset}: {e}")
            return False

    async def get_balance(self, asset: str) -> Decimal:
        """Obtém saldo disponível de um ativo"""
        try:
            if isinstance(self.client, AsyncClient):
                balance = await self.client.get_asset_balance(asset=asset)
            else:
                balance = self.client.get_asset_balance(asset=asset)
            
            if balance and 'free' in balance:
                return Decimal(str(balance['free']))
            return Decimal('0')
        except Exception as e:
            logger.error(f"❌ Erro ao obter saldo de {asset}: {e}")
            return Decimal('0')

    async def get_symbol_info(self, symbol: str):
        """Obtém informações do símbolo de forma assíncrona ou síncrona"""
        try:
            if isinstance(self.client, AsyncClient):
                return await self.client.get_symbol_info(symbol)
            return self.client.get_symbol_info(symbol)
        except Exception as e:
            logger.error(f"❌ Erro ao obter informações do símbolo {symbol}: {e}")
            return None

    def get_min_notional(self, symbol: str) -> Decimal:
        """Retorna o valor mínimo para uma ordem no par"""
        try:
            symbol_info = asyncio.get_event_loop().run_until_complete(self.get_symbol_info(symbol))
            if not symbol_info:
                return Decimal('10.0')
            
            filters = {f['filterType']: f for f in symbol_info['filters']}
            if 'MIN_NOTIONAL' in filters:
                return Decimal(str(filters['MIN_NOTIONAL']['minNotional']))
            return Decimal('10.0')
        except Exception as e:
            logger.error(f"❌ Erro ao obter min_notional para {symbol}: {e}")
            return Decimal('10.0')

    def get_lot_size(self, symbol: str) -> Dict[str, Decimal]:
        """Retorna informações sobre o tamanho do lote para o par"""
        try:
            symbol_info = asyncio.get_event_loop().run_until_complete(self.get_symbol_info(symbol))
            if not symbol_info:
                return {'min_qty': Decimal('0.00001'), 'max_qty': Decimal('9999999'), 'step_size': Decimal('0.00001')}
            
            filters = {f['filterType']: f for f in symbol_info['filters']}
            if 'LOT_SIZE' in filters:
                lot_filter = filters['LOT_SIZE']
                return {
                    'min_qty': Decimal(str(lot_filter['minQty'])),
                    'max_qty': Decimal(str(lot_filter['maxQty'])),
                    'step_size': Decimal(str(lot_filter['stepSize']))
                }
            return {'min_qty': Decimal('0.00001'), 'max_qty': Decimal('9999999'), 'step_size': Decimal('0.00001')}
        except Exception as e:
            logger.error(f"❌ Erro ao obter lot_size para {symbol}: {e}")
            return {'min_qty': Decimal('0.00001'), 'max_qty': Decimal('9999999'), 'step_size': Decimal('0.00001')}

    def normalize_quantity(self, symbol: str, quantity: Decimal) -> Decimal:
        """Normaliza a quantidade de acordo com as regras do par"""
        lot_size = self.get_lot_size(symbol)
        step_size = lot_size['step_size']

        # Arredonda para o step size mais próximo
        normalized = Decimal(str(quantity))
        if step_size != 0:
            normalized = (normalized / step_size).quantize(Decimal('1')) * step_size

        # Garante limites min/max
        normalized = max(min(normalized, lot_size['max_qty']), lot_size['min_qty'])
        return normalized

    async def execute_arbitrage(self, opportunity: Dict) -> bool:
        """Executa uma oportunidade de arbitragem

        Args:
            opportunity: Dicionário com informações da oportunidade

        Returns:
            bool: True se executou com sucesso
        """
        if not await self.validate_opportunity(opportunity):
            return False

        # Registra início do trade
        trade_id = len(self.active_trades) + 1
        trade = {
            'id': trade_id,
            'start_time': datetime.now(),
            'opportunity': opportunity,
            'status': 'started',
            'steps': [],
            'initial_balance': None,
            'stop_loss': None,
            'take_profit': None
        }
        
        try:
            # Obtém saldo inicial
            start_currency = opportunity['a_step_from']
            initial_balance = await self.get_balance(start_currency)
            trade['initial_balance'] = float(initial_balance)
            
            # Define stop loss e take profit
            trade['stop_loss'] = float(initial_balance * (1 - self.stop_loss_pct))
            trade['take_profit'] = float(initial_balance * (1 + self.take_profit_pct))
            
            self.active_trades.append(trade)
            logger.info(f"🔄 Iniciando trade #{trade_id}")

            # Executa os 3 passos da arbitragem
            steps = [
                (opportunity['a_step_from'], opportunity['a_step_to'], opportunity['a_rate']),
                (opportunity['b_step_from'], opportunity['b_step_to'], opportunity['b_rate']),
                (opportunity['c_step_from'], opportunity['c_step_to'], opportunity['c_rate'])
            ]

            current_amount = self.trade_amount
            for i, (from_coin, to_coin, rate) in enumerate(steps, 1):
                symbol = f"{from_coin}{to_coin}"

                # Verifica saldo antes de cada operação
                if not await self.check_balance(from_coin, current_amount):
                    logger.error(f"❌ Saldo insuficiente para step {i}")
                    trade['status'] = 'failed'
                    trade['error'] = f"Saldo insuficiente de {from_coin}"
                    return False

                # Calcula preço com slippage
                price = Decimal(str(rate)) * (1 + self.max_slippage)
                quantity = self.normalize_quantity(symbol, current_amount)

                # Coloca ordem com proteções
                if self.test_mode:
                    logger.info(f"Simulação: Ordem {symbol} colocada com quantidade {quantity}")
                    success = True  # Simula sucesso na execução da ordem
                else:
                    success = await self.place_order(symbol, "MARKET", quantity)
                if not success:
                    logger.error(f"❌ Falha ao executar step {i} do trade {trade_id}")
                    trade['status'] = 'failed'
                    return False

                # Verifica stop loss após cada operação
                current_balance = await self.get_balance(from_coin)
                if float(current_balance) < trade['stop_loss']:
                    logger.warning(f"🛑 Stop loss atingido no step {i}")
                    trade['status'] = 'stopped'
                    return False

                # Atualiza quantidade para próximo passo
                current_amount = quantity * Decimal(str(rate)) * (1 - self.fee_rate)

                trade['steps'].append({
                    'step': i,
                    'symbol': symbol,
                    'type': 'MARKET',
                    'quantity': str(quantity),
                    'price': str(price),
                    'result_amount': str(current_amount)
                })

            # Trade completo com sucesso
            trade['status'] = 'completed'
            trade['end_time'] = datetime.now()
            trade['final_amount'] = str(current_amount)
            self.completed_trades.append(trade)
            self.active_trades.remove(trade)

            logger.info(f"✅ Trade #{trade_id} completado com sucesso!")
            return True

        except Exception as e:
            logger.error(f"❌ Erro ao executar trade #{trade_id}: {e}")
            trade['status'] = 'failed'
            trade['error'] = str(e)
            return False

    async def validate_opportunity(self, opportunity: Dict) -> bool:
        """Valida se uma oportunidade pode ser executada"""
        try:
            # Verifica lucro mínimo considerando taxas
            profit = Decimal(str(opportunity['rate'])) - 1
            profit = profit * 100  # Converte para porcentagem
            total_fees = self.fee_rate * 3  # 3 operações
            net_profit = profit - (total_fees * 100)
            
            if net_profit < self.min_profit:
                logger.debug(
                    f"❌ Lucro insuficiente: {net_profit:.2f}% (mín: {self.min_profit}%)")
                return False

            # Verifica saldo inicial
            start_currency = opportunity['a_step_from']
            if not await self.check_balance(start_currency, self.trade_amount):
                return False

            # Verifica volume mínimo
            for step in ['a_volume', 'b_volume', 'c_volume']:
                if Decimal(str(opportunity[step])) < self.trade_amount:
                    logger.debug(f"❌ Volume insuficiente no step {step}")
                    return False

            return True

        except Exception as e:
            logger.error(f"❌ Erro ao validar oportunidade: {e}")
            return False

    async def place_order(self, symbol: str, order_type: str, quantity: Decimal) -> bool:
        """Coloca uma ordem real na exchange"""
        try:
            params = {
                'symbol': symbol,
                'side': 'MARKET',
                'type': order_type,
                'quantity': float(quantity)
            }
            
            if isinstance(self.client, AsyncClient):
                order = await self.client.create_order(**params)
            else:
                order = self.client.create_order(**params)
            
            logger.info(f"✅ Ordem {order['orderId']} executada: {symbol}")
            return True

        except BinanceAPIException as e:
            logger.error(f"❌ Erro Binance ao executar ordem: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Erro ao executar ordem: {e}")
            return False

    async def cancel_orders(self, symbol: Optional[str] = None) -> None:
        """Cancela ordens ativas de forma segura"""
        try:
            if symbol:
                # Cancela ordens para um símbolo específico usando a API spot
                if isinstance(self.client, AsyncClient):
                    result = await self.client.get_open_orders(symbol=symbol)
                    for order in result:
                        await self.client.cancel_order(
                            symbol=symbol,
                            orderId=order['orderId']
                        )
                else:
                    result = self.client.get_open_orders(symbol=symbol)
                    for order in result:
                        self.client.cancel_order(
                            symbol=symbol,
                            orderId=order['orderId']
                        )
                logger.info(f"✅ Todas as ordens de {symbol} canceladas")
            else:
                # Cancela ordens em todos os símbolos ativos
                for trade in self.active_trades:
                    for step in trade['steps']:
                        current_symbol = step['symbol']
                        if isinstance(self.client, AsyncClient):
                            result = await self.client.get_open_orders(symbol=current_symbol)
                            for order in result:
                                await self.client.cancel_order(
                                    symbol=current_symbol,
                                    orderId=order['orderId']
                                )
                        else:
                            result = self.client.get_open_orders(symbol=current_symbol)
                            for order in result:
                                self.client.cancel_order(
                                    symbol=current_symbol,
                                    orderId=order['orderId']
                                )
                logger.info("✅ Todas as ordens canceladas")
        except Exception as e:
            logger.error(f"❌ Erro ao cancelar ordens: {e}")
