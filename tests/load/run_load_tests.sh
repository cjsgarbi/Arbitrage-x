#!/bin/bash

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Iniciando testes de carga...${NC}"

# Verifica se k6 está instalado
if ! command -v k6 &> /dev/null; then
    echo -e "${RED}k6 não encontrado. Por favor, instale o k6:${NC}"
    echo "Mac: brew install k6"
    echo "Linux: sudo apt-get install k6"
    echo "Windows: choco install k6"
    exit 1
fi

# Cria diretório para relatórios se não existir
REPORT_DIR="tests/load/reports"
mkdir -p "$REPORT_DIR"

# Nome do arquivo de relatório com timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
JSON_REPORT="$REPORT_DIR/report_$TIMESTAMP.json"
HTML_REPORT="$REPORT_DIR/report_$TIMESTAMP.html"

echo -e "${YELLOW}Executando testes de Config API...${NC}"
k6 run --out json="$JSON_REPORT.config" tests/load/config_api.js

echo -e "${YELLOW}Executando testes de Trading API...${NC}"
k6 run --out json="$JSON_REPORT.trading" tests/load/trading_api.js

# Combina os resultados dos testes
jq -s '.[0] * .[1]' "$JSON_REPORT.config" "$JSON_REPORT.trading" > "$JSON_REPORT"
rm "$JSON_REPORT.config" "$JSON_REPORT.trading"

# Verifica se o teste foi executado com sucesso
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Testes concluídos com sucesso!${NC}"
else
    echo -e "${RED}Falha nos testes!${NC}"
    exit 1
fi

# Converte relatório JSON para HTML
echo -e "${YELLOW}Gerando relatório HTML...${NC}"
cat > "$HTML_REPORT" << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Relatório de Teste de Carga - $TIMESTAMP</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
</head>
<body class="bg-gray-100 p-8">
    <div class="max-w-7xl mx-auto">
        <h1 class="text-3xl font-bold mb-8">Relatório de Teste de Carga</h1>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div class="bg-white p-6 rounded-lg shadow">
                <h2 class="text-xl font-semibold mb-4">Métricas HTTP</h2>
                <div id="httpMetrics"></div>
            </div>
            <div class="bg-white p-6 rounded-lg shadow">
                <h2 class="text-xl font-semibold mb-4">Métricas WebSocket</h2>
                <div id="wsMetrics"></div>
            </div>
            <div class="bg-white p-6 rounded-lg shadow">
                <h2 class="text-xl font-semibold mb-4">Métricas de Arbitragem</h2>
                <div id="arbitrageMetrics"></div>
            </div>
            <div class="bg-white p-6 rounded-lg shadow">
                <h2 class="text-xl font-semibold mb-4">Oportunidades de Lucro</h2>
                <div id="profitMetrics"></div>
            </div>
        </div>
        <div class="mt-6 bg-white p-6 rounded-lg shadow">
            <h2 class="text-xl font-semibold mb-4">Timeline</h2>
            <div id="timeline"></div>
            <div class="mt-4">
                <h3 class="text-lg font-semibold mb-2">Sumário de Performance</h3>
                <div id="performanceSummary" class="grid grid-cols-2 md:grid-cols-4 gap-4 text-center"></div>
            </div>
        </div>
    </div>
    <script>
        fetch('$JSON_REPORT')
            .then(response => response.json())
            .then(data => {
                // Processa dados para HTTP
                // Métricas HTTP
                const httpMetrics = data.metrics.filter(m => m.type === 'http_req_duration');
                const httpData = {
                    x: httpMetrics.map(m => m.timestamp),
                    y: httpMetrics.map(m => m.value),
                    type: 'scatter',
                    name: 'HTTP Response Time'
                };
                
                Plotly.newPlot('httpMetrics', [httpData], {
                    title: 'Tempo de Resposta HTTP',
                    yaxis: { title: 'Duração (ms)' }
                });

                // Métricas WebSocket
                const wsMetrics = data.metrics.filter(m => m.type === 'ws_connect_failures');
                const wsData = {
                    x: wsMetrics.map(m => m.timestamp),
                    y: wsMetrics.map(m => m.value),
                    type: 'scatter',
                    name: 'Falhas WS'
                };
                
                Plotly.newPlot('wsMetrics', [wsData], {
                    title: 'Falhas de Conexão WebSocket',
                    yaxis: { title: 'Taxa de Falha' }
                });

                // Métricas de Arbitragem
                const arbitrageMetrics = data.metrics.filter(m => m.type === 'arbitrage_duration');
                const arbitrageData = {
                    x: arbitrageMetrics.map(m => m.timestamp),
                    y: arbitrageMetrics.map(m => m.value),
                    type: 'scatter',
                    name: 'Duração da Arbitragem'
                };
                
                Plotly.newPlot('arbitrageMetrics', [arbitrageData], {
                    title: 'Tempo de Processamento de Arbitragem',
                    yaxis: { title: 'Duração (ms)' }
                });

                // Métricas de Lucro
                const profitMetrics = data.metrics.filter(m => m.type === 'profit_opportunities');
                const profitData = {
                    x: profitMetrics.map(m => m.timestamp),
                    y: profitMetrics.map(m => m.value),
                    type: 'scatter',
                    name: 'Oportunidades de Lucro'
                };
                
                Plotly.newPlot('profitMetrics', [profitData], {
                    title: 'Oportunidades de Lucro ao Longo do Tempo',
                    yaxis: { title: 'Lucro Esperado (%)' }
                });

                // Timeline de usuários
                const vuMetrics = data.metrics.filter(m => m.type === 'vus');
                const timelineData = {
                    x: vuMetrics.map(m => m.timestamp),
                    y: vuMetrics.map(m => m.value),
                    type: 'scatter',
                    name: 'Usuários Virtuais'
                };
                
                Plotly.newPlot('timeline', [timelineData], {
                    title: 'Usuários Virtuais ao Longo do Tempo',
                    yaxis: { title: 'Usuários' }
                });

                // Sumário de Performance
                const summary = document.getElementById('performanceSummary');
                const metrics = {
                    'Média Resp. HTTP': `${(httpMetrics.reduce((a, b) => a + b.value, 0) / httpMetrics.length).toFixed(2)}ms`,
                    'Taxa de Falha WS': `${(wsMetrics.reduce((a, b) => a + b.value, 0) / wsMetrics.length * 100).toFixed(2)}%`,
                    'Média Arbitragem': `${(arbitrageMetrics.reduce((a, b) => a + b.value, 0) / arbitrageMetrics.length).toFixed(2)}ms`,
                    'Lucro Médio': `${(profitMetrics.reduce((a, b) => a + b.value, 0) / profitMetrics.length).toFixed(2)}%`
                };

                summary.innerHTML = Object.entries(metrics)
                    .map(([key, value]) => `
                        <div class="bg-gray-50 p-4 rounded">
                            <div class="text-sm text-gray-500">${key}</div>
                            <div class="text-lg font-semibold">${value}</div>
                        </div>
                    `).join('');
            });
    </script>
</body>
</html>
EOF

echo -e "${GREEN}Relatório HTML gerado: $HTML_REPORT${NC}"
echo -e "${YELLOW}Abrindo relatório no navegador...${NC}"

# Abre o relatório no navegador padrão
if [[ "$OSTYPE" == "darwin"* ]]; then
    open "$HTML_REPORT"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    xdg-open "$HTML_REPORT"
elif [[ "$OSTYPE" == "msys" ]]; then
    start "$HTML_REPORT"
fi

echo -e "${GREEN}Testes de carga concluídos!${NC}"