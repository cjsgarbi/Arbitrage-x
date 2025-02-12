import pytest
from unittest.mock import Mock, patch
import json
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from triangular_arbitrage.ui.web.config_routes import ConfigManager

class TestConfigManager:
    @pytest.fixture
    def config_manager(self, tmp_path):
        """Fixture que cria um ConfigManager com diretório temporário"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        return ConfigManager(str(config_dir))

    @pytest.fixture
    def sample_config(self):
        """Fixture com configuração de exemplo para testes"""
        return {
            "trading": {
                "min_profit": "0.2",
                "stop_loss": "1.0",
                "take_profit": "0.5",
                "trade_amount": "0.01",
                "test_mode": "true"  # Apenas monitoramento, sem enviar ordens
            },
            "monitoring": {
                "update_interval": "1.0",
                "backup_interval": "86400",
                "notify_on_trade": "true"
            }
        }

    def test_init_creates_config_dir(self, tmp_path):
        config_dir = tmp_path / "config"
        ConfigManager(str(config_dir))
        assert config_dir.exists()

    def test_load_default_config_when_file_missing(self, config_manager):
        config = config_manager.get_config()
        assert "trading" in config
        assert "monitoring" in config
        assert "rate_limits" in config
        assert "security" in config

    def test_save_and_load_config(self, config_manager, sample_config):
        # Salva configuração
        for category, values in sample_config.items():
            for key, value in values.items():
                config_manager.update_config(category, key, value)

        # Recarrega configuração
        config_manager._load_config()
        loaded_config = config_manager.get_config()

        # Verifica se os valores foram salvos corretamente
        for category, values in sample_config.items():
            for key, value in values.items():
                assert loaded_config[category][key] == value

    def test_get_specific_category(self, config_manager, sample_config):
        # Configura dados
        for category, values in sample_config.items():
            for key, value in values.items():
                config_manager.update_config(category, key, value)

        # Testa obtenção de categoria específica
        trading_config = config_manager.get_config("trading")
        assert trading_config == sample_config["trading"]

    def test_update_config_saves_history(self, config_manager):
        category = "trading"
        key = "min_profit"
        value = "0.3"

        # Atualiza configuração
        config_manager.update_config(category, key, value)

        # Verifica arquivo de histórico
        history_file = Path(config_manager.config_dir) / "config_history.jsonl"
        assert history_file.exists()

        # Lê última linha do histórico
        with open(history_file) as f:
            last_change = json.loads(f.readlines()[-1])
            assert last_change["category"] == category
            assert last_change["key"] == key
            assert last_change["value"] == value

    def test_invalid_category_returns_empty_dict(self, config_manager):
        assert config_manager.get_config("invalid_category") == {}

    def test_update_creates_new_category(self, config_manager):
        config_manager.update_config("new_category", "new_key", "new_value")
        config = config_manager.get_config()
        assert "new_category" in config
        assert config["new_category"]["new_key"] == "new_value"

    @pytest.mark.parametrize("category,key,value,expected", [
        ("trading", "min_profit", "-0.1", False),  # Valor negativo inválido
        ("trading", "trade_amount", "0", False),   # Volume zero inválido
        ("trading", "test_mode", "true", True),    # Modo monitoramento válido
        ("trading", "test_mode", "false", True),   # Modo execução válido
        ("monitoring", "update_interval", "0.01", True),  # Valor válido
        ("security", "max_daily_trades", "abc", False),  # Não numérico inválido
    ])
    def test_config_validation(self, config_manager, category, key, value, expected):
        result = config_manager.update_config(category, key, value)
        assert result == expected

    def test_config_backup_on_update(self, config_manager, sample_config):
        # Simula várias atualizações
        for category, values in sample_config.items():
            for key, value in values.items():
                config_manager.update_config(category, key, value)

        # Verifica se backup foi criado
        backup_files = list(Path(config_manager.config_dir).glob("*.backup"))
        assert len(backup_files) > 0

    def test_concurrent_updates(self, config_manager):
        import threading
        import time

        def update_config(value):
            config_manager.update_config("test", "concurrent", str(value))
            time.sleep(0.1)

        # Cria threads para updates concorrentes
        threads = []
        for i in range(10):
            t = threading.Thread(target=update_config, args=(i,))
            threads.append(t)
            t.start()

        # Aguarda todas as threads
        for t in threads:
            t.join()

        # Verifica se não houve corrupção de dados
        config = config_manager.get_config()
        assert "test" in config
        assert "concurrent" in config["test"]
        assert config["test"]["concurrent"].isdigit()

    def test_config_version_control(self, config_manager):
        # Primeira versão
        config_manager.update_config("test", "version", "1.0")
        
        # Segunda versão
        config_manager.update_config("test", "version", "2.0")

        # Verifica histórico
        history_file = Path(config_manager.config_dir) / "config_history.jsonl"
        with open(history_file) as f:
            changes = [json.loads(line) for line in f]
            
        assert len(changes) == 2
        assert changes[0]["value"] == "1.0"
        assert changes[1]["value"] == "2.0"

    def test_export_config(self, config_manager, sample_config):
        # Configura dados
        for category, values in sample_config.items():
            for key, value in values.items():
                config_manager.update_config(category, key, value)

        # Exporta configuração
        export_file = Path(config_manager.config_dir) / "export.json"
        config_manager.export_config(str(export_file))

        # Verifica arquivo exportado
        assert export_file.exists()
        with open(export_file) as f:
            exported_config = json.load(f)
            assert exported_config == config_manager.get_config()