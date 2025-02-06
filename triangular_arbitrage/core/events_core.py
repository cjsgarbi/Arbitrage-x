from typing import Dict, List, Callable, Any
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class EventsCore:
    def __init__(self):
        """Inicializa o sistema de eventos"""
        self.subscribers: Dict[str, List[Callable]] = {}
        self.event_history: List[Dict[str, Any]] = []
        self.max_history = 1000

    def subscribe(self, event_type: str, callback: Callable) -> None:
        """Registra um callback para um tipo de evento

        Args:
            event_type: Tipo do evento para se inscrever
            callback: Função a ser chamada quando o evento ocorrer
        """
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)
        logger.debug(f"Novo subscriber registrado para evento {event_type}")

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """Remove um callback de um tipo de evento

        Args:
            event_type: Tipo do evento para se desinscrever
            callback: Função a ser removida
        """
        if event_type in self.subscribers:
            try:
                self.subscribers[event_type].remove(callback)
                logger.debug(f"Subscriber removido do evento {event_type}")
            except ValueError:
                logger.warning(
                    f"Callback não encontrado para evento {event_type}")

    async def emit(self, event_type: str, data: Any = None) -> None:
        """Emite um evento para todos os subscribers

        Args:
            event_type: Tipo do evento a ser emitido
            data: Dados do evento
        """
        event = {
            'type': event_type,
            'data': data,
            'timestamp': datetime.now()
        }

        # Adiciona ao histórico
        self.event_history.append(event)
        if len(self.event_history) > self.max_history:
            self.event_history.pop(0)

        # Notifica subscribers
        if event_type in self.subscribers:
            tasks = []
            for callback in self.subscribers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        tasks.append(asyncio.create_task(callback(event)))
                    else:
                        callback(event)
                except Exception as e:
                    logger.error(f"Erro ao processar evento {event_type}: {e}")

            # Aguarda tasks assíncronas
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

        logger.debug(f"Evento {event_type} emitido com sucesso")

    def get_history(self, event_type: str = None, limit: int = None) -> List[Dict]:
        """Retorna histórico de eventos

        Args:
            event_type: Filtra por tipo de evento
            limit: Limita número de eventos retornados

        Returns:
            Lista de eventos do histórico
        """
        history = self.event_history

        if event_type:
            history = [e for e in history if e['type'] == event_type]

        if limit:
            history = history[-limit:]

        return history

    def clear_history(self) -> None:
        """Limpa histórico de eventos"""
        self.event_history.clear()
        logger.debug("Histórico de eventos limpo")
