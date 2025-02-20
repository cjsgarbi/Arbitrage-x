"""
Validador de dados em tempo real
"""
from typing import Dict, Any, List, Union, Optional
from decimal import Decimal, InvalidOperation
from datetime import datetime
from .debug_logger import debug_logger

class DataValidator:
    def __init__(self):
        self.price_precision = 8  # Precisão padrão para preços
        self.volume_precision = 8  # Precisão padrão para volumes
        
        # Limites de validação ajustados para arbitragem triangular
        self.limits = {
            'min_price': 1e-12,  # Permitir preços muito baixos
            'max_price': 1e12,   # Permitir preços muito altos
            'min_volume': 1e-6, # Volume mínimo reduzido
            'max_volume': 1e12, # Volume máximo aumentado
            'min_spread': -0.5,  # Spread mínimo mais amplo (-50%)
            'max_spread': 0.5,   # Spread máximo mais amplo (+50%)
            'max_age': 120,      # Dados válidos por até 2 minutos
            'min_profit': 0.0001 # Lucro mínimo para considerar oportunidade (0.01%)
        }

    def validate_ticker(self, ticker: Dict[str, Any]) -> bool:
        """Valida dados do ticker"""
        try:
            required_fields = ['volume', 'weightedAvgPrice', 'priceChangePercent', 'lastPrice']
            
            if not all(field in ticker for field in required_fields):
                debug_logger.log_event(
                    'validation_error',
                    'Campos obrigatórios ausentes no ticker',
                    {'missing': [f for f in required_fields if f not in ticker]}
                )
                return False

            # Valida timestamp
            timestamp = float(ticker['timestamp']) / 1000  # Converte de ms para s
            age = datetime.now().timestamp() - timestamp
            if age > self.limits['max_age']:
                debug_logger.log_event(
                    'validation_error',
                    'Dados muito antigos',
                    {'age': age, 'max_age': self.limits['max_age']}
                )
                return False

            # Valida preços
            for price_field in ['price', 'bidPrice', 'askPrice', 'lastPrice']:
                price = Decimal(str(ticker[price_field]))
                if not (self.limits['min_price'] <= float(price) <= self.limits['max_price']):
                    debug_logger.log_event(
                        'validation_error',
                        'Preço fora dos limites',
                        {'field': price_field, 'value': float(price)}
                    )
                    return False

            # Valida volume
            volume = Decimal(str(ticker['volume']))
            if not (self.limits['min_volume'] <= float(volume) <= self.limits['max_volume']):
                debug_logger.log_event(
                    'validation_error',
                    'Volume fora dos limites',
                    {'volume': float(volume)}
                )
                return False

            # Valida spread
            bid = Decimal(str(ticker['bidPrice']))
            ask = Decimal(str(ticker['askPrice']))
            spread = (ask - bid) / bid
            if not (self.limits['min_spread'] <= float(spread) <= self.limits['max_spread']):
                debug_logger.log_event(
                    'validation_error',
                    'Spread fora dos limites',
                    {'spread': float(spread)}
                )
                return False

            return True

        except (KeyError, TypeError, InvalidOperation) as e:
            debug_logger.log_event(
                'validation_error',
                'Erro ao validar ticker',
                {'error': str(e)}
            )
            return False

    def validate_orderbook(self, orderbook: Dict[str, Any]) -> bool:
        """Valida dados do livro de ordens"""
        try:
            if not orderbook.get('bids') or not orderbook.get('asks'):
                debug_logger.log_event(
                    'validation_error',
                    'Livro de ordens vazio'
                )
                return False

            # Valida estrutura
            if not all(len(level) >= 2 for level in orderbook['bids'] + orderbook['asks']):
                debug_logger.log_event(
                    'validation_error',
                    'Formato inválido de ordens'
                )
                return False

            # Valida preços e quantidades
            for side in ['bids', 'asks']:
                for price, quantity in orderbook[side]:
                    try:
                        price_dec = Decimal(str(price))
                        quantity_dec = Decimal(str(quantity))
                        
                        if not (self.limits['min_price'] <= float(price_dec) <= self.limits['max_price']):
                            debug_logger.log_event(
                                'validation_error',
                                f'Preço {side} fora dos limites',
                                {'price': float(price_dec)}
                            )
                            return False
                            
                        if not (self.limits['min_volume'] <= float(quantity_dec) <= self.limits['max_volume']):
                            debug_logger.log_event(
                                'validation_error',
                                f'Volume {side} fora dos limites',
                                {'volume': float(quantity_dec)}
                            )
                            return False
                            
                    except (InvalidOperation, TypeError) as e:
                        debug_logger.log_event(
                            'validation_error',
                            f'Erro ao validar {side}',
                            {'error': str(e)}
                        )
                        return False

            # Valida ordenação e consistência
            bid_prices = [Decimal(str(b[0])) for b in orderbook['bids']]
            ask_prices = [Decimal(str(a[0])) for a in orderbook['asks']]
            
            if bid_prices and ask_prices and bid_prices[0] >= ask_prices[0]:
                debug_logger.log_event(
                    'validation_error',
                    'Cruzamento de ordens detectado',
                    {
                        'best_bid': float(bid_prices[0]),
                        'best_ask': float(ask_prices[0])
                    }
                )
                return False

            return True

        except Exception as e:
            debug_logger.log_event(
                'validation_error',
                'Erro ao validar orderbook',
                {'error': str(e)}
            )
            return False

    def validate_trade(self, trade: Dict[str, Any]) -> bool:
        """Valida dados de trade"""
        try:
            required_fields = [
                'symbol', 'price', 'quantity', 'timestamp'
            ]
            
            if not all(field in trade for field in required_fields):
                debug_logger.log_event(
                    'validation_error',
                    'Campos obrigatórios ausentes no trade',
                    {'missing': [f for f in required_fields if f not in trade]}
                )
                return False

            # Valida timestamp
            timestamp = float(trade['timestamp']) / 1000  # Converte de ms para s
            age = datetime.now().timestamp() - timestamp
            if age > self.limits['max_age']:
                debug_logger.log_event(
                    'validation_error',
                    'Trade muito antigo',
                    {'age': age, 'max_age': self.limits['max_age']}
                )
                return False

            # Valida preço e quantidade
            price = Decimal(str(trade['price']))
            quantity = Decimal(str(trade['quantity']))
            
            if not (self.limits['min_price'] <= float(price) <= self.limits['max_price']):
                debug_logger.log_event(
                    'validation_error',
                    'Preço do trade fora dos limites',
                    {'price': float(price)}
                )
                return False
                
            if not (self.limits['min_volume'] <= float(quantity) <= self.limits['max_volume']):
                debug_logger.log_event(
                    'validation_error',
                    'Volume do trade fora dos limites',
                    {'volume': float(quantity)}
                )
                return False

            return True

        except (KeyError, TypeError, InvalidOperation) as e:
            debug_logger.log_event(
                'validation_error',
                'Erro ao validar trade',
                {'error': str(e)}
            )
            return False

# Instância global do validador
data_validator = DataValidator()