from typing import Dict, List, Optional
from decimal import Decimal
import asyncio
from datetime import datetime
import logging

from binance.client import Client
from binance.exceptions import BinanceAPIException
from ..config import BINANCE_CONFIG, TRADING_CONFIG

logger = logging.getLogger(__name__)


class TradingCore:
    def __init__(self, client: Client, simulation_mode: bool = True):
        """Inicializa o TradingCore

        Args:
            client: Cliente Binance
            simulation_mode: Se True, apenas simula as ordens sem executá-las
        """
        self.client = client
        self.simulation_mode = simulation_mode
        self.min_profit = Decimal('0.3')  # Lucro mínimo em %
        self.trade_amount = Decimal('0.01')  # Quantidade base para trades
        self.active_trades: List[Dict] = []
        self.completed_trades: List[Dict] = []
        self.is_testnet = BINANCE_CONFIG['use_testnet']

    def get_min_notional(self, symbol: str) -> Decimal:
        """Retorna o valor mínimo para uma ordem no par"""
        try:
            symbol_info = self.client.get_symbol_info(symbol)
            filters = {f['filterType']: f for f in symbol_info['filters']}
            if 'MIN_NOTIONAL' in filters:
                return Decimal(str(filters['MIN_NOTIONAL']['minNotional']))
            return Decimal('10.0')  # Valor padrão seguro
        except Exception as e:
            logger.error(f"Erro ao obter min_notional para {symbol}: {e}")
            return Decimal('10.0')

    def get_lot_size(self, symbol: str) -> Dict[str, Decimal]:
        """Retorna informações sobre o tamanho do lote para o par"""
        try:
            symbol_info = self.client.get_symbol_info(symbol)
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
            logger.error(f"Erro ao obter lot_size para {symbol}: {e}")
            return {'min_qty': Decimal('0.00001'), 'max_qty': Decimal('9999999'), 'step_size': Decimal('0.00001')}

    def normalize_quantity(self, symbol: str, quantity: Decimal) -> Decimal:
        """Normaliza a quantidade de acordo com as regras do par"""
        lot_size = self.get_lot_size(symbol)
        step_size = lot_size['step_size']

        # Arredonda para o step size mais próximo
        normalized = Decimal(str(quantity))
        if step_size != 0:
            normalized = (
                normalized / step_size).quantize(Decimal('1')) * step_size

        # Garante limites min/max
        normalized = max(
            min(normalized, lot_size['max_qty']), lot_size['min_qty'])
        return normalized

    async def execute_arbitrage(self, opportunity: Dict) -> bool:
        """Executa uma oportunidade de arbitragem

        Args:
            opportunity: Dicionário com informações da oportunidade

        Returns:
            bool: True se executou com sucesso
        """
        if not self.validate_opportunity(opportunity):
            return False

        # Registra início do trade
        trade_id = len(self.active_trades) + 1
        trade = {
            'id': trade_id,
            'start_time': datetime.now(),
            'opportunity': opportunity,
            'status': 'started',
            'steps': []
        }
        self.active_trades.append(trade)

        try:
            # Executa os 3 passos da arbitragem
            steps = [
                (opportunity['a_step_from'],
                 opportunity['a_step_to'], opportunity['a_rate']),
                (opportunity['b_step_from'],
                 opportunity['b_step_to'], opportunity['b_rate']),
                (opportunity['c_step_from'],
                 opportunity['c_step_to'], opportunity['c_rate'])
            ]

            current_amount = self.trade_amount
            for i, (from_coin, to_coin, rate) in enumerate(steps, 1):
                symbol = f"{from_coin}{to_coin}"

                # Normaliza quantidade
                quantity = self.normalize_quantity(symbol, current_amount)

                # Simula ou executa ordem
                if self.simulation_mode:
                    success = await self.simulate_order(symbol, "BUY", quantity, rate)
                else:
                    success = await self.place_order(symbol, "BUY", quantity, rate)

                if not success:
                    logger.error(
                        f"Falha ao executar passo {i} do trade {trade_id}")
                    trade['status'] = 'failed'
                    return False

                # Atualiza quantidade para próximo passo
                current_amount = quantity * Decimal(str(rate))

                trade['steps'].append({
                    'step': i,
                    'symbol': symbol,
                    'quantity': str(quantity),
                    'rate': str(rate),
                    'result_amount': str(current_amount)
                })

            # Trade completo com sucesso
            trade['status'] = 'completed'
            trade['end_time'] = datetime.now()
            trade['final_amount'] = str(current_amount)
            self.completed_trades.append(trade)
            self.active_trades.remove(trade)

            logger.info(f"Trade {trade_id} completado com sucesso!")
            return True

        except Exception as e:
            logger.error(f"Erro ao executar trade {trade_id}: {e}")
            trade['status'] = 'failed'
            trade['error'] = str(e)
            return False

    async def validate_opportunity(self, opportunity: Dict) -> bool:
        """Valida se uma oportunidade pode ser executada"""
        try:
            # Verifica lucro mínimo
            profit = (Decimal(str(opportunity['rate'])) - 1) * 100
            if profit < self.min_profit:
                return False

            # Verifica saldo (real ou demo)
            if not self.simulation_mode:
                start_currency = opportunity['a_step_from']

                if self.is_testnet:
                    # Usa saldo demo na testnet
                    balance = await self.bot_core.get_demo_balance(start_currency)
                else:
                    # Usa saldo real na mainnet
                    balance = Decimal(
                        str(await self.client.get_asset_balance(asset=start_currency))['free'])

                if balance < self.trade_amount:
                    logger.warning(
                        f"Saldo insuficiente de {start_currency}: {balance}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Erro ao validar oportunidade: {e}")
            return False

    async def simulate_order(self, symbol: str, side: str, quantity: Decimal, rate: Decimal) -> bool:
        """Simula uma ordem sem executá-la"""
        try:
            logger.info(
                f"Simulando ordem: {side} {quantity} {symbol} @ {rate}")
            await asyncio.sleep(0.1)  # Simula latência
            return True
        except Exception as e:
            logger.error(f"Erro ao simular ordem: {e}")
            return False

    async def place_order(self, symbol: str, side: str, quantity: Decimal, rate: Decimal) -> bool:
        """Coloca uma ordem real na exchange"""
        try:
            # Se estiver na testnet, usa test orders
            if self.is_testnet and TRADING_CONFIG['test_mode']:
                order = await self.client.create_test_order(
                    symbol=symbol,
                    side=side,
                    type='LIMIT',
                    timeInForce='GTC',
                    quantity=float(quantity),
                    price=float(rate)
                )
                logger.info(f"Test order simulada com sucesso: {symbol}")
                return True

            # Ordem real (testnet ou mainnet)
            order = await self.client.create_order(
                symbol=symbol,
                side=side,
                type='LIMIT',
                timeInForce='GTC',
                quantity=float(quantity),
                price=float(rate)
            )
            logger.info(f"Ordem colocada: {order['orderId']}")
            return True

        except BinanceAPIException as e:
            if self.is_testnet:
                logger.warning(f"Erro Testnet ao colocar ordem: {e}")
            else:
                logger.error(f"Erro Binance ao colocar ordem: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro ao colocar ordem: {e}")
            return False
