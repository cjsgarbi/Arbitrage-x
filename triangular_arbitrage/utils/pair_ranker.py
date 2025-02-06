from typing import Dict, List, Optional
from decimal import Decimal
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PairRanker:
    def __init__(self):
        """Inicializa o sistema de ranking de pares"""
        self.pair_stats: Dict[str, Dict] = {}
        self.ranking_window = timedelta(minutes=30)
        self.min_trades = 5
        self.max_spread = Decimal('0.02')  # 2%

    def update_pair(self, symbol: str, price: Decimal, volume: Decimal) -> None:
        """Atualiza estatísticas de um par

        Args:
            symbol: Par de trading
            price: Preço atual
            volume: Volume atual
        """
        now = datetime.now()

        if symbol not in self.pair_stats:
            self.pair_stats[symbol] = {
                'prices': [],
                'volumes': [],
                'timestamps': [],
                'last_update': now,
                'score': Decimal('0'),
                'rank': 0
            }

        stats = self.pair_stats[symbol]

        # Remove dados antigos
        cutoff = now - self.ranking_window
        while stats['timestamps'] and stats['timestamps'][0] < cutoff:
            stats['prices'].pop(0)
            stats['volumes'].pop(0)
            stats['timestamps'].pop(0)

        # Adiciona novos dados
        stats['prices'].append(price)
        stats['volumes'].append(volume)
        stats['timestamps'].append(now)
        stats['last_update'] = now

        # Atualiza score
        self._update_score(symbol)

    def _update_score(self, symbol: str) -> None:
        """Atualiza o score de um par baseado em suas estatísticas"""
        stats = self.pair_stats[symbol]

        # Precisa de dados suficientes
        if len(stats['prices']) < self.min_trades:
            stats['score'] = Decimal('0')
            return

        try:
            # Calcula volatilidade
            prices = [Decimal(str(p)) for p in stats['prices']]
            mean_price = sum(prices) / len(prices)
            variance = sum((p - mean_price) ** 2 for p in prices) / len(prices)
            volatility = (variance ** Decimal('0.5')) / mean_price

            # Calcula volume médio
            volumes = [Decimal(str(v)) for v in stats['volumes']]
            mean_volume = sum(volumes) / len(volumes)

            # Calcula spread médio
            high = max(prices)
            low = min(prices)
            spread = (high - low) / mean_price

            # Penaliza spreads muito altos
            if spread > self.max_spread:
                stats['score'] = Decimal('0')
                return

            # Score final combina volume e volatilidade
            volume_weight = Decimal('0.7')
            volatility_weight = Decimal('0.3')

            # Normaliza volume (log scale)
            volume_score = (mean_volume.ln() + Decimal('10')) / Decimal('20')
            volume_score = max(min(volume_score, Decimal('1')), Decimal('0'))

            # Normaliza volatilidade
            volatility_score = volatility / \
                Decimal('0.1')  # 10% volatilidade = score 1
            volatility_score = max(
                min(volatility_score, Decimal('1')), Decimal('0'))

            stats['score'] = (volume_score * volume_weight +
                              volatility_score * volatility_weight)

        except Exception as e:
            logger.error(f"Erro ao calcular score para {symbol}: {e}")
            stats['score'] = Decimal('0')

    def update_rankings(self) -> None:
        """Atualiza ranking de todos os pares"""
        try:
            # Ordena por score
            pairs = sorted(
                self.pair_stats.keys(),
                key=lambda s: self.pair_stats[s]['score'],
                reverse=True
            )

            # Atualiza ranks
            for rank, symbol in enumerate(pairs, 1):
                self.pair_stats[symbol]['rank'] = rank

            logger.debug(f"Rankings atualizados: {len(pairs)} pares")

        except Exception as e:
            logger.error(f"Erro ao atualizar rankings: {e}")

    def get_top_pairs(self, limit: int = 20) -> List[Dict]:
        """Retorna os pares melhor ranqueados

        Args:
            limit: Número máximo de pares a retornar

        Returns:
            Lista de dicionários com informações dos pares
        """
        try:
            pairs = sorted(
                [
                    {
                        'symbol': s,
                        'score': float(stats['score']),
                        'rank': stats['rank'],
                        'last_update': stats['last_update']
                    }
                    for s, stats in self.pair_stats.items()
                    if stats['score'] > 0
                ],
                key=lambda p: p['score'],
                reverse=True
            )
            return pairs[:limit]

        except Exception as e:
            logger.error(f"Erro ao obter top pairs: {e}")
            return []

    def get_pair_stats(self, symbol: str) -> Optional[Dict]:
        """Retorna estatísticas detalhadas de um par

        Args:
            symbol: Par de trading

        Returns:
            Dicionário com estatísticas ou None se par não encontrado
        """
        if symbol not in self.pair_stats:
            return None

        stats = self.pair_stats[symbol]
        return {
            'symbol': symbol,
            'score': float(stats['score']),
            'rank': stats['rank'],
            'last_update': stats['last_update'],
            'num_trades': len(stats['prices']),
            'latest_price': float(stats['prices'][-1]) if stats['prices'] else 0,
            'latest_volume': float(stats['volumes'][-1]) if stats['volumes'] else 0
        }
