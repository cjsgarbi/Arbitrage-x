import time
import asyncio
from typing import Dict, Optional
from datetime import datetime, timedelta
import logging
from collections import defaultdict
from dataclasses import dataclass
import aioredis
from fastapi import HTTPException

logger = logging.getLogger(__name__)

@dataclass
class RateLimit:
    """Define um limite de taxa"""
    requests: int
    window: int  # em segundos
    cost: int = 1  # peso da requisição

@dataclass
class RateLimitInfo:
    """Informações sobre o uso atual do rate limit"""
    requests: int
    window_start: float
    last_reset: float

class RateLimiter:
    def __init__(self, redis_url: Optional[str] = None):
        """Inicializa o rate limiter

        Args:
            redis_url: URL do Redis para armazenamento distribuído (opcional)
        """
        self.limits: Dict[str, Dict[str, RateLimit]] = {
            'default': {
                'global': RateLimit(1000, 3600),  # 1000 req/hora
                'burst': RateLimit(100, 60),      # 100 req/minuto
            },
            'api': {
                'global': RateLimit(10000, 3600),  # 10000 req/hora
                'ip': RateLimit(100, 60),          # 100 req/minuto por IP
                'user': RateLimit(1000, 3600),     # 1000 req/hora por usuário
            },
            'binance': {
                'orders': RateLimit(10, 1),        # 10 ordens/segundo
                'weight': RateLimit(1200, 60),     # 1200 peso/minuto
            }
        }

        # Estado em memória
        self.state: Dict[str, Dict[str, RateLimitInfo]] = defaultdict(lambda: defaultdict(
            lambda: RateLimitInfo(0, time.time(), time.time())
        ))

        # Redis para estado distribuído
        self.redis = None
        self.redis_url = redis_url

    async def initialize(self):
        """Inicializa conexão com Redis se configurado"""
        if self.redis_url:
            try:
                self.redis = await aioredis.create_redis_pool(self.redis_url)
                logger.info("✅ Conexão com Redis estabelecida")
            except Exception as e:
                logger.error(f"❌ Erro ao conectar com Redis: {e}")
                self.redis = None

    async def close(self):
        """Fecha conexão com Redis"""
        if self.redis:
            self.redis.close()
            await self.redis.wait_closed()

    async def _get_current_usage(self, key: str, scope: str) -> RateLimitInfo:
        """Obtém uso atual do rate limit

        Args:
            key: Identificador do cliente (IP, usuário, etc)
            scope: Escopo do limite (global, ip, user, etc)

        Returns:
            RateLimitInfo: Informações de uso atual
        """
        if self.redis:
            # Usa Redis para estado distribuído
            redis_key = f"ratelimit:{scope}:{key}"
            data = await self.redis.hgetall(redis_key)
            if data:
                return RateLimitInfo(
                    int(data[b'requests']),
                    float(data[b'window_start']),
                    float(data[b'last_reset'])
                )
        
        # Usa estado em memória
        return self.state[scope][key]

    async def _update_usage(self, key: str, scope: str, info: RateLimitInfo):
        """Atualiza uso do rate limit

        Args:
            key: Identificador do cliente
            scope: Escopo do limite
            info: Novas informações de uso
        """
        if self.redis:
            redis_key = f"ratelimit:{scope}:{key}"
            await self.redis.hmset(redis_key, {
                'requests': info.requests,
                'window_start': info.window_start,
                'last_reset': info.last_reset
            })
            # Define TTL para expirar dados antigos
            await self.redis.expire(redis_key, 3600)
        else:
            self.state[scope][key] = info

    def _should_reset(self, limit: RateLimit, info: RateLimitInfo) -> bool:
        """Verifica se deve resetar o contador

        Args:
            limit: Limite configurado
            info: Informações de uso atual

        Returns:
            bool: True se deve resetar
        """
        return time.time() - info.window_start >= limit.window

    async def check_rate_limit(
        self, 
        key: str, 
        category: str = 'default',
        scope: str = 'global',
        cost: int = 1
    ) -> bool:
        """Verifica se uma requisição está dentro dos limites

        Args:
            key: Identificador do cliente
            category: Categoria do limite (default, api, binance)
            scope: Escopo do limite (global, ip, user, etc)
            cost: Peso da requisição

        Returns:
            bool: True se requisição é permitida

        Raises:
            HTTPException: Se limite é excedido
        """
        try:
            limit = self.limits[category][scope]
            info = await self._get_current_usage(key, scope)

            # Verifica se deve resetar janela
            if self._should_reset(limit, info):
                info = RateLimitInfo(0, time.time(), time.time())

            # Verifica limite
            if info.requests + cost > limit.requests:
                reset_in = int(info.window_start + limit.window - time.time())
                raise HTTPException(
                    status_code=429,
                    detail={
                        'error': 'Rate limit exceeded',
                        'reset_in': reset_in,
                        'limit': limit.requests,
                        'remaining': limit.requests - info.requests
                    }
                )

            # Atualiza contadores
            info.requests += cost
            info.last_reset = time.time()
            await self._update_usage(key, scope, info)

            return True

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Erro ao verificar rate limit: {e}")
            return True  # Em caso de erro, permite requisição

    async def get_status(self, key: str, category: str = 'default', scope: str = 'global') -> Dict:
        """Retorna status atual do rate limit

        Args:
            key: Identificador do cliente
            category: Categoria do limite
            scope: Escopo do limite

        Returns:
            Dict: Status atual com limites e uso
        """
        try:
            limit = self.limits[category][scope]
            info = await self._get_current_usage(key, scope)

            if self._should_reset(limit, info):
                info = RateLimitInfo(0, time.time(), time.time())

            return {
                'limit': limit.requests,
                'remaining': limit.requests - info.requests,
                'reset': int(info.window_start + limit.window),
                'window': limit.window,
                'cost': limit.cost
            }

        except Exception as e:
            logger.error(f"❌ Erro ao obter status do rate limit: {e}")
            return {}

    async def wait_if_needed(self, key: str, category: str = 'default', scope: str = 'global') -> None:
        """Espera se necessário para respeitar limite
        
        Args:
            key: Identificador do cliente
            category: Categoria do limite
            scope: Escopo do limite
        """
        try:
            status = await self.get_status(key, category, scope)
            if status.get('remaining', 1) <= 0:
                wait_time = status.get('reset', 0) - int(time.time())
                if wait_time > 0:
                    logger.warning(f"⏳ Aguardando {wait_time}s pelo rate limit")
                    await asyncio.sleep(wait_time)
        except Exception as e:
            logger.error(f"❌ Erro ao verificar espera: {e}")

    async def clear(self, key: str, category: str = 'default', scope: str = 'global'):
        """Limpa contadores do rate limit

        Args:
            key: Identificador do cliente
            category: Categoria do limite
            scope: Escopo do limite
        """
        try:
            if self.redis:
                redis_key = f"ratelimit:{scope}:{key}"
                await self.redis.delete(redis_key)
            else:
                if scope in self.state and key in self.state[scope]:
                    del self.state[scope][key]
        except Exception as e:
            logger.error(f"❌ Erro ao limpar rate limit: {e}")