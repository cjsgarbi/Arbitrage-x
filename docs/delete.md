# Arquivos e Pastas Dispensáveis

## Visão Geral
Este documento lista os arquivos e pastas que podem ser removidos sem afetar o funcionamento do fluxo da IA ao frontend.

## Estrutura de Arquivos Dispensáveis

triangular_arbitrage/
├── memory.md               # Documentação antiga -- não nexer 
├── memory2.md             # Documentação antiga -- não mexer 
├── debug.py              # Script de debug não usado no fluxo
├── test.py               # Script de teste local   -- naã afetou 
├── CHANGELOG.md          # Histórico de mudanças   -- nap afetou 
├── playwright.config.ts  # Configuração de testes e2e  -- não  afertou
├── tailwind.config.js    # Não usado no frontend atual -- Naõ afetou
├── setup.py             # Script de instalação alternativo ´-- naã afetou 
├── libs/                # Módulos JS legados
│   ├── BotCore.js      # Versão antiga em JS --- Afetou o repo 
│   ├── CurrencyCore.js # Substituído por currency_core.py -- não afetou
│   ├── CurrencySelector.js # Funcionalidade movida para IA -- não afetou 
│   ├── DBCore.js       # Não usado no fluxo atual    --- não afetou 
│   ├── DBHelpers.js    # Não usado no fluxo atual   --- nao afetou 
│   ├── EventsCore.js   # Versão JS obsoleta         --- naõ afetou 
│   ├── LoggerCore.js   # Substituído por logger.py  --- não afetou
│   ├── PairRanker.js   # Substituído pela IA        --- não afetou 
│   ├── TradingCore.js  # Versão JS obsoleta         --- não afetou 
│   └── UI.js           # Interface antiga           --- não afetou 
├── tests/               # Testes não essenciais para execução --- resolvendo 
│   ├── e2e/           # Testes end-to-end
│   ├── integration/   # Testes de integração
│   └── load/          # Testes de carga
└── utils/              # Utilitários não essenciais
    ├── alert_system.py      # Sistema de alertas opcional -- naõ afetou
    ├── backup_manager.py    # Backup não crítico       --- resolvendo
    ├── pair_ranker.py      # Substituído pela IA       --- afetou o repo  
    ├── rate_limiter.py     # Limitação opcional       --- resolvendo
    └── performance_metrics.py # Métricas não críticas  --- resolvendo

## Arquivos de Configuração Dispensáveis
- .dockerignore        # Configuração Docker não usada
- Dockerfile          # Não necessário para execução local
- pyrightconfig.json  # Configuração IDE
- tsconfig.json      # Configuração TypeScript não usada

## Detalhamento

1. **Arquivos de Documentação**
   - memory.md, memory2.md: Documentação antiga substituída
   - CHANGELOG.md: Histórico não afeta execução

2. **Scripts de Desenvolvimento**
   - debug.py: Apenas para desenvolvimento
   - test.py: Testes locais
   - setup.py: Instalação alternativa não necessária

3. **Pasta libs/**
   - Contém versões JavaScript antigas das funcionalidades
   - Todas as funções foram migradas para Python

4. **Pasta tests/**
   - Testes não são necessários para execução
   - Podem ser removidos sem afetar o sistema

5. **Utilitários Opcionais**
   - alert_system.py: Sistema de alertas secundário
   - backup_manager.py: Backup não crítico
   - pair_ranker.py: Função movida para IA
   - rate_limiter.py: Limitação opcional
   - performance_metrics.py: Métricas não críticas

6. **Configurações de Desenvolvimento**
   - Arquivos Docker não usados
   - Configurações de IDE e TypeScript

Todos estes arquivos e pastas podem ser removidos mantendo apenas a estrutura essencial descrita em estruturanew.md, que contém todos os componentes necessários para o funcionamento do fluxo da IA ao frontend.