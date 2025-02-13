<p align="center">
  <img src="illustration.jpeg" width="250px" height="250px" alt="Triangular illustration">
</p>

# Arbitrage Opportunity Detection by OctoBot [1.2.0](https://github.com/Drakkar-Software/Triangular-Arbitrage/blob/master/CHANGELOG.md)
[![PyPI](https://img.shields.io/pypi/v/OctoBot-Triangular-Arbitrage.svg)](https://pypi.python.org/pypi/OctoBot-Triangular-Arbitrage/)
[![Dockerhub](https://img.shields.io/docker/pulls/drakkarsoftware/octobot-triangular-arbitrage.svg?logo=docker)](https://hub.docker.com/r/drakkarsoftware/octobot-triangular-arbitrage)

This Python-based project utilizes the [ccxt library](https://github.com/ccxt/ccxt) and the [OctoBot library](https://github.com/Drakkar-Software/OctoBot) to detect potential arbitrage opportunities across multiple assets in cryptocurrency markets. It identifies profitable cycles where you can trade through a series of assets and return to the original asset with a potential gain, making it applicable for arbitrage strategies beyond just triangular cycles.

## Description

Arbitrage trading is a process where you trade from one asset or currency to another, and then continue trading through a series of assets until you eventually return to the original asset or currency. The goal is to exploit price differences between multiple assets to generate a profit. For example, you could start with USD, buy BTC, use the BTC to buy ETH, trade the ETH for XRP, and finally sell the XRP back to USD. If the prices are favorable throughout the cycle, you could end up with more USD than you started with. This project provides a method to identify the best arbitrage opportunities in a multi-asset cycle, given a list of last prices for different cryptocurrency pairs. It's a versatile and effective tool for anyone interested in cryptocurrency trading and arbitrage strategies across various currencies and assets.

## Getting Started

### Dependencies

* Python 3.10

### Crie e ative o venv:
```bash
python -m venv venv

venv\Scripts\activate 
```
### Installing

```bash
pip install -r requirements.txt
```

### Usage
Start detection by running:
```bash
python3 main.py
python main.py ## para rodar windows
```

Example output on Binance:
```
-------------------------------------------
New 2.33873% binanceus opportunity:
# 1. buy DOGE with BTC at 552486.18785
# 2. sell DOGE for USDT at 0.12232
# 3. buy ETH with USDT at 0.00038
# 4. buy ADA with ETH at 7570.02271
# 5. sell ADA for USDC at 0.35000
# 6. buy SOL with USDC at 0.00662
# 7. sell SOL for BTC at 0.00226
-------------------------------------------
```

### Configuration
To change the exchange edit `main.py` `exchange_name` value to the desired exchange. It should match the exchange [ccxt id value](https://github.com/ccxt/ccxt?tab=readme-ov-file#certified-cryptocurrency-exchanges)

You can also provide a list of symbol to ignore when calling `run_detection` using `ignored_symbols` and a list of symbol to whitelist using `whitelisted_symbols`.

## Help

You can join any OctoBot community to get help [![Discord](https://img.shields.io/discord/530629985661222912.svg?logo=discord&label=Discord)](https://octobot.click/gh-discord) [![Telegram Chat](https://img.shields.io/badge/telegram-chat-green.svg?logo=telegram&label=Telegram)](https://octobot.click/gh-telegram)

# Sistema de Arbitragem Triangular

## Visão Geral
Este projeto implementa um sistema de arbitragem triangular otimizado para velocidade, usando Python para detecção de oportunidades e Ruby para execução rápida de trades.

## Estrutura do Projeto
```
Triangular-Arbitrage/           # Raiz do projeto
├── triangular_arbitrage/       # Código Python principal
│   ├── binance_connector.py    # Conexão direta com Binance
│   └── detector.py            # Detector de arbitragem
├── ruby_executor/             # Executor rápido em Ruby
│   ├── bin/                  # Executáveis Ruby
│   └── lib/                  # Código Ruby
├── requirements.txt          # Dependências Python
└── config/                  # Configurações
```

## Instalação Passo a Passo

### 1. Preparar Ambiente Python (IMPORTANTE: Execute na raiz do projeto)
```bash
# Clone o repositório
git clone [URL_DO_REPO]
cd Triangular-Arbitrage

# Criar ambiente virtual
python -m venv venv

# Ativar ambiente (Windows)
venv\Scripts\activate
# OU Linux/Mac
# source venv/bin/activate

# IMPORTANTE: Atualizar pip primeiro
python -m pip install --upgrade pip

# Instalar dependências (use exatamente este comando)
python -m pip install -r requirements.txt
```

### 2. Instalar Ruby (Para execução rápida de trades)
```bash
# Windows: Baixe Ruby+Devkit 3.4.1-2 (x64)
# https://rubyinstaller.org/downloads/

# Durante instalação selecione:
# [x] MSYS2 base installation
# [x] MSYS2 and MINGW development toolchain

# Após instalar, execute:
ridk install
# Quando solicitado, digite: 1,3
```

### 3. Configurar Ruby Executor
```bash
# Instalar Bundler (globalmente)
gem install bundler

# Entrar na pasta ruby_executor
cd ruby_executor

# Instalar dependências Ruby
bundle install
```

## Execução do Sistema

### 1. Scanner Python (Terminal 1)
```bash
# Na raiz do projeto
cd Triangular-Arbitrage
python main.py
```

### 2. Executor Ruby (Terminal 2)
```bash
# Na pasta ruby_executor
cd ruby_executor
bundle exec bin/trade_executor
```

## Características do Sistema

### Detecção de Oportunidades (Python)
- Conexão WebSocket direta com Binance
- Cache local de preços
- Análise de grafos para arbitragem
- Baixa latência na detecção

### Execução de Trades (Ruby)
- Event Loop otimizado
- Execução assíncrona de ordens
- Cache distribuído
- Comunicação via ZeroMQ

## Configuração

### 1. Credenciais Binance
```yaml
# config/credentials.yml
binance:
  api_key: "sua_api_key"
  api_secret: "seu_api_secret"
```

### 2. Parâmetros de Trading
```yaml
# config/trading_params.yml
min_profit: 0.5  # Lucro mínimo (%)
max_trade_size: 100  # Tamanho máximo do trade em USDT
```

## Verificação da Instalação

Execute estes comandos para verificar se tudo está correto:

```bash
# Verificar Python e dependências
python --version
python -m pip list | findstr "binance websockets aiohttp numpy"

# Verificar Ruby
ruby -v
gem list | findstr "eventmachine faye-websocket zmq"
```

## Solução de Problemas

### Erros Comuns

1. **Erro ao instalar dependências**:
   ```bash
   # Use sempre
   python -m pip install -r requirements.txt
   # NÃO use apenas 'pip install'
   ```

2. **Erro no Ruby**:
   ```bash
   # Certifique-se de instalar com DevKit
   # Use ridk install após a instalação
   ```

## Contribuição

1. Fork o repositório
2. Crie sua branch (`git checkout -b feature/SuaFeature`)
3. Commit suas mudanças (`git commit -m 'Adiciona feature'`)
4. Push para a branch (`git push origin feature/SuaFeature`)
5. Abra um Pull Request

## Licença

Este projeto está licenciado sob a [sua licença] - veja o arquivo LICENSE.md para detalhes.

# Bot de Arbitragem Triangular

Bot para identificar e executar oportunidades de arbitragem triangular na Binance.

## ⚠️ IMPORTANTE: Modos de Operação

O bot opera EXCLUSIVAMENTE com a Binance real. O modo de operação é controlado pela configuração `TEST_MODE`:

### TEST_MODE=true (Padrão)
- Conecta à Binance real
- Monitora preços reais
- Detecta oportunidades reais
- NÃO envia ordens para a Binance
- Ideal para análise e monitoramento de oportunidades

### TEST_MODE=false
- Conecta à Binance real
- Monitora preços reais
- Detecta oportunidades reais
- ENVIA ordens reais para a Binance
- Use com cautela, ordens serão executadas com dinheiro real

Para alterar o modo:
1. Edite o arquivo `.env`:
```bash
# Modo de monitoramento (não envia ordens)
TEST_MODE=true

# Modo de execução (envia ordens reais)
TEST_MODE=false
```

## Características

- Monitoramento em tempo real via WebSocket da Binance
- Interface de usuário com métricas detalhadas
- Sistema de ranking de pares mais promissores
- Logs detalhados e histórico de operações
- Banco de dados SQLite para persistência
- Tratamento robusto de erros e reconexões
- Detecção de oportunidades em tempo real
- Execução rápida de ordens quando em modo execução

## Requisitos

- Python 3.8+
- Conta na Binance (para modo real)
- API Key e Secret da Binance

## Instalação

1. Clone o repositório:
```bash
git clone https://github.com/seu-usuario/triangular-arbitrage.git
cd triangular_arbitrage
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Configure suas credenciais:
- Crie um arquivo `.env` na raiz do projeto
- Adicione suas credenciais da Binance:
```
BINANCE_API_KEY=sua_api_key
BINANCE_API_SECRET=seu_api_secret
```

## Uso

### Modo Simulação

Para executar o bot em modo simulação (sem realizar trades reais):

```bash
python main.py --test
```

### Modo Real

Para executar o bot em modo real (realizará trades se encontrar oportunidades):

```bash
python main.py
```

### Configurações

Você pode ajustar várias configurações no arquivo `config.py`:

- `MIN_PROFIT`: Lucro mínimo para executar arbitragem (default: 0.3%)
- `TRADE_AMOUNT`: Quantidade base para trades
- `UPDATE_INTERVAL`: Intervalo de atualização dos preços
- `MAX_CONCURRENT_TRADES`: Máximo de trades simultâneos
- `BASE_CURRENCIES`: Moedas base para triangulação

## Estrutura do Projeto

```
triangular_arbitrage/
├── core/
│   ├── bot_core.py        # Núcleo do bot
│   ├── currency_core.py   # Lógica de arbitragem
│   ├── trading_core.py    # Execução de trades
│   └── events_core.py     # Sistema de eventos
├── utils/
│   ├── logger.py         # Sistema de logs
│   ├── db_helpers.py     # Helpers de banco
│   └── pair_ranker.py    # Ranking de pares
└── ui/
    └── display.py        # Interface do usuário
```

## Logs e Dados

- Logs são salvos em `logs/`
- Banco de dados em `data/bot.db`
- Relatórios de trades em `logs/trades.json`

## Segurança

- Nunca compartilhe suas credenciais da API
- Use o modo simulação para testar estratégias
- Comece com valores pequenos em modo real
- Monitore os logs para detectar problemas

## Contribuindo

1. Fork o projeto
2. Crie uma branch para sua feature
3. Commit suas mudanças
4. Push para a branch
5. Abra um Pull Request

## Licença

Este projeto está licenciado sob a MIT License - veja o arquivo LICENSE para detalhes.

## Disclaimer

Trading de criptomoedas envolve riscos significativos. Use este bot por sua conta e risco. Os autores não são responsáveis por perdas financeiras.
````
