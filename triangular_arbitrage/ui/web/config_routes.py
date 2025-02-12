from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, Optional
from pydantic import BaseModel
import logging
import json
from pathlib import Path
from datetime import datetime

from .auth import get_current_active_user, User
from ...utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

class ConfigUpdate(BaseModel):
    """Modelo para atualização de configuração"""
    category: str
    key: str
    value: str

router = APIRouter(prefix="/api/config", tags=["config"])

class ConfigManager:
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "bot_config.json"
        self._load_config()

    def _load_config(self):
        """Carrega configurações do arquivo"""
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    self.config = json.load(f)
            except Exception as e:
                logger.error(f"❌ Erro ao carregar configurações: {e}")
                self.config = self._get_default_config()
        else:
            self.config = self._get_default_config()
            self._save_config()

    def _save_config(self):
        """Salva configurações no arquivo"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Erro ao salvar configurações: {e}")

    def _get_default_config(self) -> Dict:
        """Retorna configuração padrão"""
        return {
            "trading": {
                "min_profit": "0.2",
                "stop_loss": "1.0",
                "take_profit": "0.5",
                "trade_amount": "0.01",
                "max_slippage": "0.2",
                "fee_rate": "0.1"
            },
            "monitoring": {
                "update_interval": "1.0",
                "backup_interval": "86400",
                "retention_days": "30",
                "notify_on_trade": "true",
                "notify_on_error": "true",
                "min_profit_notify": "0.5"
            },
            "rate_limits": {
                "api_requests_per_hour": "10000",
                "api_requests_per_minute": "100",
                "orders_per_second": "10",
                "weight_per_minute": "1200"
            },
            "security": {
                "max_daily_trades": "1000",
                "max_trade_amount": "0.05",
                "max_daily_volume": "1.0"
            }
        }

    def get_config(self, category: Optional[str] = None) -> Dict:
        """Retorna configurações

        Args:
            category: Categoria específica (opcional)

        Returns:
            Dict: Configurações solicitadas
        """
        if category:
            return self.config.get(category, {})
        return self.config

    def update_config(self, category: str, key: str, value: str) -> bool:
        """Atualiza uma configuração

        Args:
            category: Categoria da configuração
            key: Chave a atualizar
            value: Novo valor

        Returns:
            bool: True se atualizado com sucesso
        """
        try:
            if category not in self.config:
                self.config[category] = {}
            
            self.config[category][key] = value
            self._save_config()
            
            # Salva histórico de alterações
            history_file = self.config_dir / "config_history.jsonl"
            with open(history_file, 'a') as f:
                change = {
                    'timestamp': datetime.now().isoformat(),
                    'category': category,
                    'key': key,
                    'value': value
                }
                f.write(json.dumps(change) + '\n')
            
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar configuração: {e}")
            return False

def init_config_routes(rate_limiter: RateLimiter) -> APIRouter:
    """Inicializa rotas de configuração"""
    config_manager = ConfigManager()

    @router.get("")
    async def get_all_config(
        request: Request,
        current_user: User = Depends(get_current_active_user)
    ):
        """Retorna todas as configurações"""
        await rate_limiter.check_rate_limit(
            key=current_user.username,
            category='api',
            scope='user'
        )
        return config_manager.get_config()

    @router.get("/{category}")
    async def get_category_config(
        category: str,
        request: Request,
        current_user: User = Depends(get_current_active_user)
    ):
        """Retorna configurações de uma categoria"""
        await rate_limiter.check_rate_limit(
            key=current_user.username,
            category='api',
            scope='user'
        )
        return config_manager.get_config(category)

    @router.post("/update")
    async def update_config(
        config_update: ConfigUpdate,
        request: Request,
        current_user: User = Depends(get_current_active_user)
    ):
        """Atualiza uma configuração"""
        await rate_limiter.check_rate_limit(
            key=current_user.username,
            category='api',
            scope='user'
        )
        
        success = config_manager.update_config(
            config_update.category,
            config_update.key,
            config_update.value
        )
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Erro ao atualizar configuração"
            )
        
        return {"status": "success", "message": "Configuração atualizada"}

    @router.get("/history")
    async def get_config_history(
        request: Request,
        current_user: User = Depends(get_current_active_user)
    ):
        """Retorna histórico de alterações"""
        await rate_limiter.check_rate_limit(
            key=current_user.username,
            category='api',
            scope='user'
        )
        
        history_file = Path("config/config_history.jsonl")
        if not history_file.exists():
            return {"changes": []}
            
        changes = []
        try:
            with open(history_file) as f:
                for line in f:
                    changes.append(json.loads(line))
            return {"changes": changes[-100:]}  # Retorna últimas 100 alterações
        except Exception as e:
            logger.error(f"❌ Erro ao ler histórico: {e}")
            raise HTTPException(
                status_code=500,
                detail="Erro ao ler histórico de configurações"
            )

    return router