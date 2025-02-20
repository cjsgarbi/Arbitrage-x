# Estrutura Completa do Fluxo da IA ao Frontend

## Visão Geral
Este documento descreve a estrutura essencial do fluxo desde a Inteligência Artificial (IA) até a interface do usuário (frontend), incluindo apenas os componentes diretamente conectados neste fluxo.

## Estrutura de Arquivos

triangular_arbitrage/
├── main.py                 # Ponto de entrada do sistema
├── config.py              # Configurações do sistema
├── core/                  # Núcleo do sistema
│   ├── bot_core.py       # Controle central do bot
│   ├── ai_pair_finder.py # IA para seleção de pares
│   ├── binance_websocket.py # Conexão WebSocket com Binance
│   ├── trading_core.py    # Processamento de trades
│   ├── metrics_manager.py # Gerenciamento de métricas
│   ├── events_core.py    # Gerenciamento de eventos
│   └── currency_core.py  # Processamento de moedas
├── ui/                    # Interface do usuário
│   ├── display.py        # Formatação de dados
│   └── web/              # Dashboard web
│       ├── app.py        # Servidor FastAPI
│       └── static/       # Assets web
│           ├── index.html # Página principal
│           ├── css/      # Estilos
│           │   └── main.css # Estilos principais
│           └── js/       # Scripts frontend
│               ├── websocket-manager.js # Gerencia WebSocket
│               ├── arbitrage-table.js  # Exibe oportunidades
│               └── metrics-manager.js  # Gerencia métricas
└── utils/                # Utilitários essenciais
    ├── data_validator.py # Validação de dados
    ├── error_handler.py  # Tratamento de erros
    ├── logger.py        # Sistema de logs
    ├── dashboard_logger.py # Logs do dashboard
    └── debug_logger.py  # Logs de debug

## Fluxo de Dados

1. **Camada de IA e Processamento**
   - ai_pair_finder.py analisa mercado e seleciona pares
   - bot_core.py coordena processamento
   - trading_core.py processa trades
   - metrics_manager.py coleta métricas
   - currency_core.py processa moedas
   - events_core.py gerencia eventos

2. **Camada de Validação e Logs**
   - data_validator.py valida todos os dados
   - error_handler.py trata erros
   - logger.py registra operações
   - debug_logger.py registra debug
   - dashboard_logger.py registra eventos do dashboard

3. **Camada de Comunicação**
   - binance_websocket.py conecta com exchange
   - app.py gerencia WebSocket com frontend
   - display.py formata dados

4. **Camada de Frontend**
   - index.html fornece interface
   - websocket-manager.js gerencia conexão
   - arbitrage-table.js exibe oportunidades
   - metrics-manager.js atualiza métricas

## Fluxo de Execução

1. IA (ai_pair_finder.py) seleciona pares
2. data_validator.py valida dados recebidos
3. bot_core.py coordena processamento
4. trading_core.py e currency_core.py processam
5. metrics_manager.py coleta métricas
6. error_handler.py e loggers monitoram
7. app.py transmite via WebSocket
8. Frontend processa e exibe dados

Esta estrutura representa o fluxo completo, funcional e validado desde a análise pela IA até a exibição no frontend, incluindo todos os componentes essenciais de validação e monitoramento.
