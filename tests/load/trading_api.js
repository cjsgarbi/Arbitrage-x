import http from 'k6/http';
import ws from 'k6/ws';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Métricas customizadas
const errorRate = new Rate('errors');
const wsConnectFailRate = new Rate('ws_connect_failures');
const profitTrend = new Trend('profit_opportunities');
const arbitrageDuration = new Trend('arbitrage_duration');

// Configurações dos testes
export const options = {
    stages: [
        { duration: '2m', target: 30 },  // Ramp-up para 30 usuários
        { duration: '5m', target: 30 },  // Teste de estabilidade
        { duration: '2m', target: 60 },  // Ramp-up para carga média
        { duration: '5m', target: 60 },  // Teste de carga média
        { duration: '2m', target: 100 }, // Ramp-up para carga alta
        { duration: '5m', target: 100 }, // Teste de carga alta
        { duration: '2m', target: 0 },   // Ramp-down
    ],
    thresholds: {
        'http_req_duration': ['p(95)<800', 'p(99)<1500'],
        'errors': ['rate<0.05'],
        'ws_connect_failures': ['rate<0.05'],
        'arbitrage_duration': ['p(95)<2000'],
    },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const WS_URL = __ENV.WS_URL || 'ws://localhost:8000/ws';

// Função auxiliar de autenticação
function getAuthToken() {
    const loginRes = http.post(`${BASE_URL}/token`, {
        username: 'admin',
        password: 'admin123'
    });

    check(loginRes, {
        'login successful': (r) => r.status === 200,
    });

    if (loginRes.status !== 200) {
        errorRate.add(1);
        return null;
    }

    return JSON.parse(loginRes.body).access_token;
}

// Teste principal
export default function () {
    const token = getAuthToken();
    if (!token) return;

    const params = {
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
        },
    };

    // Grupo de testes de trading
    {
        // Busca oportunidades de arbitragem
        const start = Date.now();
        const opportunitiesRes = http.get(`${BASE_URL}/api/trading/opportunities`, params);
        check(opportunitiesRes, {
            'get opportunities status is 200': (r) => r.status === 200,
            'opportunities data valid': (r) => {
                const data = JSON.parse(r.body);
                return Array.isArray(data.opportunities);
            },
        }) || errorRate.add(1);

        // Registra duração da busca de oportunidades
        arbitrageDuration.add(Date.now() - start);

        // Se encontrou oportunidades, registra os lucros potenciais
        if (opportunitiesRes.status === 200) {
            const data = JSON.parse(opportunitiesRes.body);
            data.opportunities.forEach(opp => {
                profitTrend.add(parseFloat(opp.expectedProfit));
            });
        }

        // Simula execução de trade
        if (Math.random() < 0.3) { // 30% de chance de executar trade
            const tradeRes = http.post(`${BASE_URL}/api/trading/execute`, JSON.stringify({
                pair1: 'BTC/USDT',
                pair2: 'ETH/BTC',
                pair3: 'ETH/USDT',
                amount: '0.01'
            }), params);

            check(tradeRes, {
                'trade execution status is 200': (r) => r.status === 200,
                'trade response valid': (r) => {
                    const data = JSON.parse(r.body);
                    return data.status === 'executed' || data.status === 'simulated';
                },
            }) || errorRate.add(1);
        }

        // Busca histórico de trades
        const historyRes = http.get(`${BASE_URL}/api/trading/history?limit=10`, params);
        check(historyRes, {
            'get history status is 200': (r) => r.status === 200,
            'history data valid': (r) => {
                const data = JSON.parse(r.body);
                return Array.isArray(data.trades);
            },
        }) || errorRate.add(1);

        sleep(1);
    }

    // Teste de WebSocket para atualizações em tempo real
    {
        const wsRes = ws.connect(WS_URL, params, function (socket) {
            socket.on('open', () => {
                socket.send(JSON.stringify({
                    type: 'subscribe',
                    channels: ['opportunities', 'trades']
                }));
            });

            socket.on('message', (data) => {
                const msg = JSON.parse(data);
                check(msg, {
                    'ws message type valid': (m) => ['opportunity', 'trade'].includes(m.type),
                    'ws message has data': (m) => m.data !== undefined,
                }) || errorRate.add(1);

                if (msg.type === 'opportunity') {
                    profitTrend.add(parseFloat(msg.data.expectedProfit));
                }
            });

            socket.on('error', () => {
                wsConnectFailRate.add(1);
            });

            // Mantém conexão por 30 segundos
            socket.setTimeout(function () {
                socket.close();
            }, 30000);
        });

        check(wsRes, {
            'ws connected successfully': (r) => r && r.status === 101,
        }) || wsConnectFailRate.add(1);
    }

    sleep(Math.random() * 3 + 2); // 2-5 segundos entre iterações
}

export function setup() {
    console.log('Iniciando testes de trading API...');
    return { startTime: Date.now() };
}

export function teardown(data) {
    console.log(`Testes finalizados! Duração: ${(Date.now() - data.startTime) / 1000}s`);
}