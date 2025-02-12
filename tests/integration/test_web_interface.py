import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import json
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from triangular_arbitrage.ui.web.app import WebDashboard
from triangular_arbitrage.ui.web.auth import add_auth_router, User

class TestWebInterface:
    @pytest.fixture
    def mock_bot_core(self):
        """Mock do BotCore para testes"""
        return Mock(
            running=True,
            get_stats=lambda: {
                'opportunities_found': 10,
                'trades_executed': 5,
                'successful_trades': 4,
                'failed_trades': 1,
                'total_profit': '0.123',
                'test_mode': True  # Modo de monitoramento ativo
            }
        )

    @pytest.fixture
    def test_client(self, mock_bot_core):
        """Cliente de teste para a API"""
        dashboard = WebDashboard(mock_bot_core)
        return TestClient(dashboard.app)

    @pytest.fixture
    def auth_headers(self):
        """Headers de autenticação para testes"""
        return {
            'Authorization': 'Bearer test_token'
        }

    @pytest.fixture
    def mock_user(self):
        """Mock de usuário autenticado"""
        return User(username="testuser", disabled=False)

    def test_dashboard_requires_auth(self, test_client):
        """Testa se dashboard requer autenticação"""
        response = test_client.get("/")
        assert response.status_code == 401

    def test_config_page_requires_auth(self, test_client):
        """Testa se página de configuração requer autenticação"""
        response = test_client.get("/config")
        assert response.status_code == 401

    def test_successful_login(self, test_client):
        """Testa login bem sucedido"""
        response = test_client.post(
            "/token",
            data={"username": "admin", "password": "admin123"}
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_failed_login(self, test_client):
        """Testa login com credenciais inválidas"""
        response = test_client.post(
            "/token",
            data={"username": "wrong", "password": "wrong"}
        )
        assert response.status_code == 401

    def test_config_update_flow(self, test_client, auth_headers, mock_user):
        """Testa fluxo completo de atualização de configuração"""
        with patch('triangular_arbitrage.ui.web.auth.get_current_active_user', return_value=mock_user):
            # Obtém configuração atual
            response = test_client.get("/api/config", headers=auth_headers)
            assert response.status_code == 200
            initial_config = response.json()

            # Atualiza configuração
            update = {
                "category": "trading",
                "key": "min_profit",
                "value": "0.5"
            }
            response = test_client.post(
                "/api/config/update",
                headers=auth_headers,
                json=update
            )
            assert response.status_code == 200

            # Verifica se atualização foi aplicada
            response = test_client.get("/api/config", headers=auth_headers)
            assert response.status_code == 200
            updated_config = response.json()
            assert updated_config["trading"]["min_profit"] == "0.5"

    def test_theme_persistence(self, test_client, auth_headers, mock_user):
        """Testa persistência do tema escolhido"""
        with patch('triangular_arbitrage.ui.web.auth.get_current_active_user', return_value=mock_user):
            # Define tema
            response = test_client.post(
                "/api/preferences/theme",
                headers=auth_headers,
                json={"theme": "dark"}
            )
            assert response.status_code == 200

            # Verifica se tema foi salvo
            response = test_client.get("/api/preferences", headers=auth_headers)
            assert response.status_code == 200
            assert response.json()["theme"] == "dark"

    def test_websocket_connection(self, test_client, auth_headers):
        """Testa conexão WebSocket"""
        with test_client.websocket_connect("/ws") as websocket:
            # Envia token de autenticação
            websocket.send_text(auth_headers["Authorization"])
            
            # Recebe primeira atualização
            data = websocket.receive_json()
            assert "status" in data
            assert "stats" in data
            assert "opportunities" in data

    def test_rate_limiting(self, test_client, auth_headers, mock_user):
        """Testa rate limiting da API"""
        with patch('triangular_arbitrage.ui.web.auth.get_current_active_user', return_value=mock_user):
            # Faz múltiplas requisições rápidas
            responses = []
            for _ in range(5):
                response = test_client.get("/api/config", headers=auth_headers)
                responses.append(response.status_code)

            # Verifica se alguma requisição foi limitada
            assert 429 in responses

    def test_config_validation(self, test_client, auth_headers, mock_user):
        """Testa validação de configurações"""
        with patch('triangular_arbitrage.ui.web.auth.get_current_active_user', return_value=mock_user):
            # Tenta atualizar com valor inválido
            update = {
                "category": "trading",
                "key": "min_profit",
                "value": "-1.0"  # Valor inválido
            }
            response = test_client.post(
                "/api/config/update",
                headers=auth_headers,
                json=update
            )
            assert response.status_code == 400

    def test_config_history(self, test_client, auth_headers, mock_user):
        """Testa histórico de alterações de configuração"""
        with patch('triangular_arbitrage.ui.web.auth.get_current_active_user', return_value=mock_user):
            # Faz algumas alterações
            updates = [
                {"category": "trading", "key": "min_profit", "value": "0.3"},
                {"category": "trading", "key": "min_profit", "value": "0.4"},
                {"category": "trading", "key": "min_profit", "value": "0.5"}
            ]
            
            for update in updates:
                test_client.post(
                    "/api/config/update",
                    headers=auth_headers,
                    json=update
                )

            # Verifica histórico
            response = test_client.get("/api/config/history", headers=auth_headers)
            assert response.status_code == 200
            history = response.json()["changes"]
            assert len(history) >= len(updates)
            
            # Verifica ordem cronológica
            for i in range(1, len(history)):
                assert history[i]["timestamp"] > history[i-1]["timestamp"]

    def test_concurrent_config_updates(self, test_client, auth_headers, mock_user):
        """Testa atualizações concorrentes de configuração"""
        import threading
        import time

        with patch('triangular_arbitrage.ui.web.auth.get_current_active_user', return_value=mock_user):
            def update_config(value):
                update = {
                    "category": "test",
                    "key": "concurrent",
                    "value": str(value)
                }
                test_client.post(
                    "/api/config/update",
                    headers=auth_headers,
                    json=update
                )
                time.sleep(0.1)

            # Cria threads para updates concorrentes
            threads = []
            for i in range(5):
                t = threading.Thread(target=update_config, args=(i,))
                threads.append(t)
                t.start()

            # Aguarda todas as threads
            for t in threads:
                t.join()

            # Verifica estado final
            response = test_client.get("/api/config", headers=auth_headers)
            assert response.status_code == 200
            config = response.json()
            assert "test" in config
            assert "concurrent" in config["test"]
            assert config["test"]["concurrent"].isdigit()

    def test_trading_mode_display(self, test_client, auth_headers, mock_user):
        """Testa se o modo de operação é exibido corretamente"""
        with patch('triangular_arbitrage.ui.web.auth.get_current_active_user', return_value=mock_user):
            response = test_client.get("/api/status", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            
            # Verifica se o modo está claramente indicado
            assert "mode" in data
            assert data["mode"] in ["monitoring", "execution"]
            assert "test_mode" in data
            
            if data["test_mode"]:
                assert data["mode"] == "monitoring"
                assert "⚠️ Modo Monitoramento - Ordens NÃO são enviadas" in data["status_message"]
            else:
                assert data["mode"] == "execution"
                assert "🚨 Modo Execução - Ordens SERÃO enviadas" in data["status_message"]