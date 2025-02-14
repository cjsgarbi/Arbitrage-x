# Estrutura do Repositório

Este documento fornece um guia detalhado da estrutura do repositório para novos desenvolvedores.

## 1. Arquivos de Configuração (Raiz)

| Arquivo | Descrição |
|---------|-----------|
| `.env.example` | Template para variáveis de ambiente necessárias |
| `.gitignore` | Lista de arquivos e diretórios ignorados pelo git |
| `CHANGELOG.md` | Histórico de mudanças do projeto |
| `Dockerfile` | Configuração para construção do container Docker |
| `MANIFEST.in` | Especifica arquivos incluídos na distribuição Python |
| `package.json` | Dependências e scripts Node.js |
| `requirements.txt` | Lista de dependências Python |
| `setup.py` | Script de instalação do pacote Python |
| `tsconfig.json` | Configurações do TypeScript |
| `pyrightconfig.json` | Configurações do verificador estático Python |

## 2. Dados e Backups (`data/`)

```
data/
├── arbitrage.db           # Banco de dados principal SQLite
└── backups/              # Diretório de backups automáticos
    ├── config/           # Backups das configurações
    └── manifest_*.json   # Manifestos de backup
```

## 3. Documentação (`docs/`)

```
docs/
├── architecture.md       # Documentação da arquitetura do sistema
├── docs.md              # Documentação geral do projeto
└── memory.md            # Status de implementação e progresso
```

## 4. Executor Ruby (`ruby_executor/`)

Sistema complementar em Ruby para execução de trades:
```
ruby_executor/
├── bin/                 # Scripts executáveis
├── config/              # Arquivos de configuração
└── lib/                 # Bibliotecas Ruby
```

## 5. Testes (`tests/`)

### Testes Unitários
- `test_config.py` - Testes de configuração
- `test_detector.py` - Testes do detector de arbitragem
- `test_logging.py` - Testes do sistema de logging
- `test_themes.py` - Testes de temas da UI

### Testes E2E
```
tests/e2e/
├── test_config_flow.py  # Testes de fluxo de configuração
└── test_load.py         # Testes de carga
```

### Testes de Integração
```
tests/integration/
└── test_web_interface.py  # Testes da interface web
```

### Testes de Carga
```
tests/load/
├── config_api.js          # Testes de API de configuração
├── trading_api.js         # Testes de API de trading
└── run_load_tests.sh      # Script para executar testes de carga
```

## 6. Core da Aplicação (`triangular_arbitrage/`)

### Core (Python)
```
triangular_arbitrage/core/
├── bot_core.py          # Núcleo principal do bot
├── currency_core.py     # Lógica de moedas e câmbio
├── trading_core.py      # Lógica de trading
└── events_core.py       # Sistema de eventos
```

### Bibliotecas JavaScript
```
triangular_arbitrage/libs/
├── BotCore.js          # Core do bot em JavaScript
├── CurrencyCore.js     # Lógica de moedas
├── DBCore.js           # Acesso ao banco de dados
├── EventsCore.js       # Sistema de eventos
├── LoggerCore.js       # Sistema de logging
├── PairRanker.js       # Ranqueamento de pares
└── UI.js              # Interface do usuário
```

### Interface Web
```
triangular_arbitrage/ui/web/
├── app.py             # Servidor principal FastAPI
├── auth.py            # Sistema de autenticação
├── config_routes.py   # Rotas de configuração
└── static/           # Frontend
    ├── index.html    # Página principal
    ├── config.html   # Página de configuração
    ├── css/         # Estilos
    └── js/          # JavaScript
```

### Utilitários
```
triangular_arbitrage/utils/
├── backup_manager.py    # Gerenciamento de backups
├── dashboard_logger.py  # Logger do dashboard
├── db_helpers.py       # Helpers do banco de dados
├── log_config.py       # Configuração de logs
├── pair_ranker.py      # Ranqueamento de pares
└── rate_limiter.py     # Limitador de requisições
```

## 7. Scripts Principais

| Script | Descrição |
|--------|-----------|
| `main.py` | Ponto de entrada principal da aplicação |
| `debug.py` | Ferramentas e utilitários de debug |
| `test.py` | Runner de testes principal |

## Componentes do Sistema

1. **Core**: Implementa a lógica principal de arbitragem e trading
2. **UI**: Interface do usuário web e dashboard
3. **Utils**: Ferramentas de suporte e utilitários
4. **Tests**: Sistema completo de testes
5. **Data**: Sistema de persistência e backups
6. **Docs**: Documentação do projeto
7. **Ruby Executor**: Sistema auxiliar para execução de trades

O sistema foi projetado de forma modular, permitindo que cada componente seja mantido e escalado independentemente. Esta arquitetura facilita:

- Desenvolvimento paralelo
- Testes isolados
- Manutenção simplificada
- Escalabilidade independente
- Integração contínua
