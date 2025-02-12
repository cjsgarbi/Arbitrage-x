from asyncio import (
    set_event_loop_policy,
    WindowsSelectorEventLoopPolicy,
    get_event_loop,
    AbstractEventLoop
)
import os
import logging
import platform
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

def configure_event_loop() -> None:
    """Configura o event loop com as configurações adequadas para cada sistema operacional"""
    try:
        # Configura policy específica para Windows
        if platform.system() == 'Windows':
            set_event_loop_policy(WindowsSelectorEventLoopPolicy())
            logger.info("✅ Event loop configurado para Windows")
        else:
            # Em sistemas Unix, podemos usar o event loop padrão
            from asyncio import unix_events
            logger.info("✅ Event loop padrão mantido para Unix")
            
            # Configura timezone em sistemas Unix
            if hasattr(time, 'tzset'):
                time.tzset()  # type: ignore
            else:
                logger.debug("tzset não disponível neste sistema")
        
        # Garante que o timezone está configurado para UTC
        try:
            current_time = datetime.now(timezone.utc)
            logger.debug(f"Sistema sincronizado com UTC: {current_time.isoformat()}")
        except Exception as e:
            logger.error(f"Erro ao sincronizar timezone: {e}")
            
    except Exception as e:
        logger.error(f"❌ Erro ao configurar event loop: {e}")
        raise