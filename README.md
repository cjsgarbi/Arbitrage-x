# Triangular Arbitrage Bot

Bot de arbitragem triangular que usa IA para identificar e executar oportunidades de arbitragem na Binance.

## Características

- Análise em tempo real de oportunidades
- Integração com IA para validação de trades
- Dois modos de operação (teste e produção)
- Sistema de cache inteligente
- Gestão automática de conexões
- Análise de histórico para aprendizado contínuo

## Estrutura do Projeto

```
triangular_arbitrage/
├── core/                      # Núcleo do sistema
│   ├── ai/                   # Componentes de IA
│   │   ├── arbitrage_analyzer.py
│   │   └── huggingface_config.py
│   ├── bot_core.py           # Core do bot
│   ├── connection_manager.py # Gestão de conexões
│   ├── currency_core.py      # Lógica de moedas
│   └── trading_core.py       # Execução de trades
├── utils/                    # Utilitários
└── ui/                       # Interface web
```

## Modos de Operação

### Modo Teste (test_mode: true)

- Conecta à Binance e recebe dados em tempo real
- Detecta oportunidades usando IA
- Simula execuções sem enviar ordens reais
- Permite ajuste de estratégias sem risco
- Armazena resultados para análise

### Modo Produção (test_mode: false)

- Mesma análise e detecção de oportunidades
- Executa ordens reais na Binance
- Validações mais rigorosas
- Requer histórico de sucesso
- Proteções adicionais de risco

## Configuração

1. Crie um arquivo `.env` baseado no `.env.example`:
```env
BINANCE_API_KEY=sua_api_key
BINANCE_API_SECRET=seu_api_secret
TEST_MODE=true  # ou false para produção
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

## Uso

### Exemplo Básico

```python
from triangular_arbitrage.core.bot_core import BotCore
import asyncio

async def main():
    bot = BotCore()
    if await bot.initialize():
        await bot.start()

asyncio.run(main())
```

### Exemplo com Script

Use o script de exemplo fornecido:
```bash
python examples/bot_usage.py
```

## Segurança

- Modo teste ativado por padrão
- Validações rigorosas em produção
- Proteções contra erros de execução
- Sistema de backup automático
- Logs detalhados de operações

## Componentes Principais

### BotCore
- Gerencia o fluxo principal do bot
- Coordena outros componentes
- Gerencia estado e recursos

### ConnectionManager
- Gerencia conexões com a Binance
- WebSocket para dados em tempo real
- Reconexão automática

### ArbitrageAnalyzer
- Análise de oportunidades com IA
- Validação baseada em histórico
- Cálculo de scores de confiança

## Contribuindo

1. Fork o repositório
2. Crie uma branch: `git checkout -b feature/nova-feature`
3. Faça commit das alterações: `git commit -am 'Add nova feature'`
4. Push para a branch: `git push origin feature/nova-feature`
5. Crie um Pull Request

## Licença

MIT License - veja o arquivo [LICENSE](LICENSE) para detalhes.

## Avisos

- Use em produção por sua conta e risco
- Teste extensivamente antes de usar com dinheiro real
- Mantenha suas chaves API seguras
- Monitore operações constantemente em produção
