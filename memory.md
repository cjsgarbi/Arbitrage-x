# Status da Integração Backend-Frontend: Oportunidades de Arbitragem
# Melhorias Propostas para Detecção de Arbitragem

## Problemas Identificados

### 1. Pares Limitados
- Atualmente monitorando apenas 5 pares: BTCUSDT, ETHUSDT, BNBUSDT, ETHBTC, BNBBTC
- Lista muito restrita de base pairs: BTC, ETH, BNB, USDT, BUSD
- Não inclui outras stablecoins populares como USDC

### 2. Filtragem Restritiva
- Dados são descartados se latência > 1000ms (muito restritivo)
- Pares são considerados "recentes" apenas se < 5s
- Oportunidades são mostradas apenas se profit > 0

### 3. Cálculo de Arbitragem
- Não considera taxas de trading
- Não considera profundidade do mercado
- Não verifica liquidez mínima

### 4. Monitoramento Insuficiente
- Falta logging detalhado das etapas de cálculo
- Não mostra oportunidades próximas do break-even
- Não mantém histórico de oportunidades

## Propostas de Melhorias

### 1. Expandir Pares
- Adicionar mais pares base (incluir USDC, DAI)
- Carregar lista dinâmica de pares da Binance
- Priorizar pares com maior volume

### 2. Ajustar Filtros
- Aumentar tolerância de latência para 2000ms
- Aumentar janela de "recentes" para 10s
- Mostrar oportunidades com profit > -0.1% (ver tendências)

### 3. Melhorar Cálculos
- Incluir taxas de trading no cálculo
- Verificar profundidade do livro de ordens
- Implementar verificação de liquidez mínima

### 4. Adicionar Monitoramento
- Logging detalhado de cada etapa
- Histórico de oportunidades
- Métricas de mercado

## O que já está implementado

### Documentação:
- Estrutura completa do repositório em docs/estrutura.md
- Arquitetura frontend/backend em docs/front_back.md
- Guia detalhado para novos desenvolvedores

### Frontend:
- Interface completa para exibição das oportunidades
- Sistema de auto-refresh
- Formatação de rotas e timestamps
- Modal de análise detalhada
- Monitor em tempo real flutuante
- Indicadores visuais de status e lucro

### WebSocket:
- Gerenciador de conexões implementado
- Sistema de reconexão automática
- Subscrição a tópicos específicos
- Manipulação de eventos e callbacks

### Binance Service:
- Conexão WebSocket com a Binance
- Sistema de subscrição a símbolos
- Gerenciamento de callbacks por símbolo
- Busca de informações detalhadas dos pares

## O que precisa ser implementado/conectado

### Endpoints Backend:
- `/api/analyze-route` para análise detalhada de rotas
- Endpoint WebSocket para streaming dos top 10 pares
- Endpoint para dados de monitoramento em tempo real

### Integrações:
- Conectar o `opportunities.js` ao backend para receber dados em tempo real
- Implementar o streaming de dados do par BTC para os 10 grupos principais
- Conectar o monitor em tempo real aos dados da Binance

### Funcionalidades:
- Implementar a lógica de cálculo de lucro em tempo real
- Adicionar validação de volume mínimo
- Implementar filtros de liquidez

## Próximos passos sugeridos

1. [] Implementar o endpoint `/api/analyze-route` no backend 
2. [] Configurar o streaming WebSocket para os top 10 pares
3. [] Conectar o frontend aos novos endpoints
4. [] Implementar a lógica de cálculo em tempo real 
5. [] Adicionar validações e filtros de segurança 

Voce deve inprementar todos esses itens sempre  mantendo o restante do repo e focando nos objetivos de memory sem fazer mudanças radicas que possam prejudicar o repo e use os aquivos e pastas do repo, vc nao pode fazer nada sem antes consultar o memory.md , faça por etapa de eliminaçao marcando os itens imprementados e em cada estapa teste e se não tiver erros vc passa para proxima etapa ate terminar o objetivo de memory .