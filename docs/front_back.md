# Frontend e Backend do Sistema de Arbitragem

Este documento explica a estrutura e interação entre o frontend e backend do sistema.

## Frontend (Interface do Usuário)

Localizado em: `triangular_arbitrage/ui/web/static/`

### 1. Arquivos HTML
- `index.html`: Dashboard principal
  - Mostra oportunidades de arbitragem em tempo real
  - Exibe monitoramento de pares
  - Interface para análise de rotas
- `config.html`: Página de configurações
  - Configuração de parâmetros do bot
  - Ajustes de conexão com a Binance
  - Preferências do usuário

### 2. JavaScript
- `js/opportunities.js`: Gerenciamento de oportunidades de arbitragem
  - Lista oportunidades ativas
  - Atualiza dados em tempo real
  - Filtra e ordena oportunidades

- `js/top-pairs.js`: Monitoramento dos principais pares
  - Exibe top 10 pares mais lucrativos
  - Atualiza métricas em tempo real
  - Mostra volume e lucro potencial

- `js/realtime-monitor.js`: Monitor em tempo real
  - Interface flutuante de monitoramento
  - Acompanhamento de pares específicos
  - Alertas e notificações

- `js/websocket-manager.js`: Gerenciador de conexões WebSocket
  - Mantém conexão com backend
  - Gerencia reconexão automática
  - Distribui mensagens para componentes

- `js/analysis.js`: Análise detalhada de rotas
  - Modal de análise profunda
  - Cálculos de risco e lucro
  - Visualização de rotas

- `js/services/binance-service.js`: Serviço de conexão com Binance
  - Interface com API da Binance
  - Cache de dados
  - Gestão de taxa de requisições

### 3. CSS
- `css/main.css`: Estilos principais
  - Layout do dashboard
  - Temas claro/escuro
  - Componentes reutilizáveis

- `css/opportunities.css`: Estilos específicos de oportunidades
  - Tabelas de oportunidades
  - Cards de análise
  - Indicadores visuais

## Backend (Servidor e Lógica de Negócio)

Localizado em: `triangular_arbitrage/`

### 1. Core (`triangular_arbitrage/core/`)
- `bot_core.py`: Núcleo principal do bot
  - Gerenciamento do ciclo de vida
  - Coordenação de componentes
  - Estado global do sistema

- `currency_core.py`: Gerenciamento de moedas e cálculos
  - Lógica de arbitragem
  - Cálculos de lucro
  - Validações de volume

- `trading_core.py`: Lógica de trading
  - Execução de ordens
  - Gestão de posições
  - Controle de risco

- `binance_websocket.py`: Conexão WebSocket com Binance
  - Stream de preços em tempo real
  - Gestão de conexão
  - Processamento de eventos

- `events_core.py`: Gerenciamento de eventos
  - Sistema de eventos interno
  - Propagação de atualizações
  - Sincronização de componentes

### 2. API e WebSocket (`triangular_arbitrage/ui/web/`)
- `app.py`: Servidor principal e endpoints da API
  - Rotas REST
  - Servidor WebSocket
  - Middleware e autenticação

- `config_routes.py`: Rotas de configuração
  - Endpoints de configuração
  - Validação de parâmetros
  - Persistência de configurações

- `auth.py`: Autenticação
  - Controle de acesso
  - Gestão de sessões
  - Segurança

### 3. Utilitários (`triangular_arbitrage/utils/`)
- `backup_manager.py`: Gerenciamento de backups
  - Backup automático
  - Restauração de dados
  - Rotação de logs

- `dashboard_logger.py`: Sistema de logging
  - Logs estruturados
  - Monitoramento de erros
  - Métricas de performance

- `rate_limiter.py`: Controle de taxa de requisições
  - Limitação de requisições
  - Proteção contra sobrecarga
  - Equilíbrio de carga

## Fluxo de Dados

1. **Conexão Inicial**
   - Frontend inicializa conexão WebSocket via `websocket-manager.js`
   - Backend aceita conexão em `app.py`
   - Autenticação é validada

2. **Streaming de Dados**
   - Backend recebe dados da Binance via `binance_websocket.py`
   - Dados são processados em `currency_core.py`
   - Oportunidades são detectadas e calculadas

3. **Atualização em Tempo Real**
   - Backend envia atualizações via WebSocket
   - Frontend recebe e distribui dados
   - Interface atualiza componentes relevantes

4. **Interação do Usuário**
   - Usuário interage com interface
   - Requisições são enviadas ao backend
   - Respostas são processadas e exibidas

5. **Monitoramento**
   - Sistema monitora performance
   - Logs são gerados
   - Backups são realizados

Esta arquitetura garante:
- Separação clara de responsabilidades
- Alta performance em tempo real
- Manutenção simplificada
- Escalabilidade independente
- Resiliência e recuperação automática
