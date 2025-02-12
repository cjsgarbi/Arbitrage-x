import http from 'k6/http';
import ws from 'k6/ws';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

// Métricas customizadas
const errorRate = new Rate('errors');
const wsConnectFailRate = new Rate('ws_connect_failures');

// Configurações dos testes
export const options = {
    stages: [
        { duration: '1m', target: 50 },  // Ramp-up para 50 usuários
        { duration: '3m', target: 50 },  // Mantém 50 usuários
        { duration: '1m', target: 100 }, // Ramp-up para 100
        { duration: '3m', target: 100 }, // Teste de stress
        { duration: '1m', target: 0 },   // Ramp-down
    ],
    thresholds: {
        'http_req_duration': ['p(95)<500'], // 95% das requisições abaixo de 500ms
        'errors': ['rate<0.1'],            // Taxa de erro abaixo de 10%
        'ws_connect_failures': ['rate<0.1'] // Falhas de WS abaixo de 10%
    },
};

// Dados de teste
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const WS_URL = __ENV.WS_URL || 'ws://localhost:8000/ws';

// Funções auxiliares
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

    // Grupo de testes da API REST
    {
        // Busca configurações
        const configRes = http.get(`${BASE_URL}/api/config`, params);
        check(configRes, {
            'get config status is 200': (r) => r.status === 200,
            'get config has data': (r) => JSON.parse(r.body).trading !== undefined,
        }) || errorRate.add(1);

        // Atualiza configuração
        const updateRes = http.post(`${BASE_URL}/api/config/update`, JSON.stringify({
            category: 'trading',
            key: 'min_profit',
            value: '0.5'
        }), params);
        check(updateRes, {
            'update config status is 200': (r) => r.status === 200,
        }) || errorRate.add(1);

        // Busca histórico
        const historyRes = http.get(`${BASE_URL}/api/config/history`, params);
        check(historyRes, {
            'get history status is 200': (r) => r.status === 200,
            'history has changes': (r) => JSON.parse(r.body).changes.length > 0,
        }) || errorRate.add(1);

        sleep(1);
    }

    // Teste de WebSocket
    {
        const wsRes = ws.connect(WS_URL, params, function (socket) {
            socket.on('open', () => {
                socket.send(token);
            });

            socket.on('message', (data) => {
                const msg = JSON.parse(data);
                check(msg, {
                    'ws message has status': (m) => m.status !== undefined,
                    'ws message has stats': (m) => m.stats !== undefined,
                }) || errorRate.add(1);
            });

            socket.on('error', () => {
                wsConnectFailRate.add(1);
            });

            // Mantém conexão por 10 segundos
            socket.setTimeout(function () {
                socket.close();
            }, 10000);
        });

        check(wsRes, {
            'ws connected successfully': (r) => r && r.status === 101,
        }) || wsConnectFailRate.add(1);
    }

    sleep(Math.random() * 3 + 2); // 2-5 segundos entre iterações
}

// Configuração de setup
export function setup() {
    console.log('Iniciando teste de carga...');
    return { startTime: Date.now() };
}

// Configuração de teardown
export function teardown(data) {
    console.log(`Teste finalizado! Duração: ${(Date.now() - data.startTime) / 1000}s`);
}