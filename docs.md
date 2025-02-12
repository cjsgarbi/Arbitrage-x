# Documentação Detalhada do Sistema de Arbitragem

## Arquitetura do Sistema

### 1. Componente Python (Detecção)
O componente Python é responsável pela detecção rápida de oportunidades usando:
- Conexão WebSocket direta com a Binance (sempre API real)
- Cache local de preços
- Análise de grafos para identificar ciclos de arbitragem
- Modo de teste para operação segura (não envia ordens)

### 2. Componente Ruby (Execução)
O componente Ruby é otimizado para execução rápida de trades:
- Event Loop eficiente
- Execução assíncrona de ordens na Binance real
- Cache distribuído
- Comunicação via ZeroMQ

### 3. Modos de Operação

O sistema opera exclusivamente com a API real da Binance, com dois modos de operação:

#### TEST_MODE=true (Modo Seguro)
- Conecta à API real da Binance
- Monitora mercados em tempo real
- Detecta oportunidades reais
- NÃO envia ordens para execução
- Ideal para testar estratégias sem risco

#### TEST_MODE=false (Modo Execução)
- Conecta à API real da Binance
- Monitora mercados em tempo real
- Detecta oportunidades reais
- ENVIA ordens reais para execução
- Requer monitoramento constante

## Instalação Detalhada

### 1. Preparação do Ambiente

#### 1.1 Python (IMPORTANTE: Execute na raiz)
```bash
# Clone e prepare o ambiente
git clone [URL_DO_REPO]
cd Triangular-Arbitrage

# Criar e ativar venv
python -m venv venv
venv\Scripts\activate     # Windows
source venv/bin/activate  # Linux/Mac

# CRUCIAL: Atualizar pip primeiro
python -m pip install --upgrade pip

# Instalar dependências (use exatamente este comando)
python -m pip install -r requirements.txt

# Iniciar o bot
python main.py
```

### 2. Verificação da Instalação

#### 2.1 Python
```bash
# Na raiz do projeto
python --version
python -m pip list | findstr "binance websockets aiohttp numpy"

# Teste de importação
python -c "import binance; import numpy; import networkx; print('OK')"
```

### 3. Configurações

1. Configure o arquivo .env com suas credenciais da Binance:
```
BINANCE_API_KEY=sua_api_key_aqui
BINANCE_API_SECRET=sua_api_secret_aqui
```

2. O sistema está configurado para:
- Usar a API real da Binance
- Operar em modo de teste por padrão (não executa ordens reais)
- Monitorar oportunidades de arbitragem
- Calcular lucros potenciais sem risco

3. Para habilitar execução real de ordens:
- Edite TRADING_CONFIG em config.py
- Altere 'test_mode': True para False

## Execução do Sistema

### 1. Detector Python
```bash
# Terminal 1 - Na raiz
cd Triangular-Arbitrage
python main.py
```

### 2. Executor Ruby
```bash
# Terminal 2 - Em ruby_executor
cd ruby_executor
bundle exec bin/trade_executor
```

## Monitoramento e Logs

### 1. Logs Python
- `logs/detector.log`: Oportunidades detectadas
- `logs/binance.log`: Conexão com a exchange

### 2. Logs Ruby
- `ruby_executor/logs/executor.log`: Execução de trades
- `ruby_executor/logs/zmq.log`: Comunicação

## Recomendações de Uso

1. Monitor logs regularmente
2. Verifique saldos antes de desativar modo teste
3. Mantenha backups do banco de dados
4. Observe as métricas de desempenho
