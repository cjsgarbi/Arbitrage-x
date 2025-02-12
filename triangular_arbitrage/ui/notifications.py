import logging
import asyncio
from typing import Optional, Dict
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError
from decimal import Decimal

logger = logging.getLogger(__name__)

class NotificationManager:
    def __init__(self, token: str, chat_id: str, min_profit: Decimal = Decimal('0.005')):
        """Gerenciador de notificações

        Args:
            token: Token do bot Telegram
            chat_id: ID do chat para enviar mensagens
            min_profit: Lucro mínimo para notificar (default: 0.5%)
        """
        self.token = token
        self.chat_id = chat_id
        self.min_profit = min_profit
        self.bot: Optional[Bot] = None
        self.enabled = bool(token and chat_id)
        
        if self.enabled:
            self.bot = Bot(token=token)
            logger.info("✅ Sistema de notificações inicializado")
        else:
            logger.warning("⚠️ Sistema de notificações desabilitado - Token ou Chat ID não configurados")

    async def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """Envia mensagem para o Telegram

        Args:
            message: Mensagem a ser enviada
            parse_mode: Modo de parse do texto (HTML/Markdown)

        Returns:
            bool: True se enviou com sucesso
        """
        if not self.enabled:
            return False

        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=parse_mode
            )
            return True
        except TelegramError as e:
            logger.error(f"❌ Erro ao enviar mensagem Telegram: {e}")
            return False

    async def notify_opportunity(self, opportunity: Dict) -> bool:
        """Notifica sobre nova oportunidade de arbitragem

        Args:
            opportunity: Dados da oportunidade

        Returns:
            bool: True se notificou com sucesso
        """
        profit = (Decimal(str(opportunity['rate'])) - 1) * 100
        if profit < self.min_profit:
            return False

        message = (
            "🔥 <b>Nova Oportunidade de Arbitragem</b>\n\n"
            f"📈 Lucro: {profit:.2f}%\n"
            f"💰 Volume: {opportunity['a_volume']} BTC\n\n"
            f"Rota:\n"
            f"1. {opportunity['a_step_from']} ➔ {opportunity['a_step_to']}\n"
            f"2. {opportunity['b_step_from']} ➔ {opportunity['b_step_to']}\n"
            f"3. {opportunity['c_step_from']} ➔ {opportunity['c_step_to']}\n\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )

        return await self.send_message(message)

    async def notify_trade_executed(self, trade: Dict) -> bool:
        """Notifica sobre trade executado

        Args:
            trade: Dados do trade

        Returns:
            bool: True se notificou com sucesso
        """
        profit = Decimal(str(trade['final_amount'])) - Decimal(str(trade['initial_balance']))
        if profit < self.min_profit:
            return False

        message = (
            "✅ <b>Trade Completado</b>\n\n"
            f"🔢 ID: #{trade['id']}\n"
            f"💰 Lucro: {profit:.8f} BTC\n"
            f"⌛ Duração: {(trade['end_time'] - trade['start_time']).total_seconds():.1f}s\n\n"
            "Passos:\n"
        )

        for step in trade['steps']:
            message += f"➔ {step['symbol']}: {step['quantity']} @ {step['price']}\n"

        message += f"\n⏰ {datetime.now().strftime('%H:%M:%S')}"

        return await self.send_message(message)

    async def notify_error(self, error: str, trade_id: Optional[int] = None) -> bool:
        """Notifica sobre erro no sistema

        Args:
            error: Mensagem de erro
            trade_id: ID do trade relacionado (opcional)

        Returns:
            bool: True se notificou com sucesso
        """
        message = (
            "❌ <b>Erro no Sistema</b>\n\n"
            f"{'Trade #' + str(trade_id) + '\n' if trade_id else ''}"
            f"Erro: {error}\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )

        return await self.send_message(message)

    async def notify_status(self, stats: Dict) -> bool:
        """Envia relatório de status do bot

        Args:
            stats: Estatísticas do bot

        Returns:
            bool: True se notificou com sucesso
        """
        message = (
            "📊 <b>Status do Bot</b>\n\n"
            f"✨ Oportunidades: {stats['opportunities_found']}\n"
            f"💰 Trades: {stats['trades_executed']}\n"
            f"📈 Sucesso: {stats['successful_trades']}\n"
            f"📉 Falhas: {stats['failed_trades']}\n"
            f"💵 Lucro Total: {stats['total_profit']} BTC\n"
            f"⌛ Uptime: {stats['uptime']}\n\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )

        return await self.send_message(message)

    async def start_status_loop(self, bot_core, interval: int = 3600):
        """Inicia loop de envio de status periódicos

        Args:
            bot_core: Instância do BotCore
            interval: Intervalo em segundos (default: 1 hora)
        """
        while True:
            try:
                await self.notify_status(bot_core.get_stats())
            except Exception as e:
                logger.error(f"❌ Erro ao enviar status: {e}")
            await asyncio.sleep(interval)