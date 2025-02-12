import pytest
from unittest.mock import Mock, patch
import json
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from triangular_arbitrage.ui.web.static.js.themes import ThemeManager

class TestThemeManager:
    @pytest.fixture
    def theme_manager(self):
        return ThemeManager()

    @pytest.fixture
    def mock_local_storage(self):
        with patch('triangular_arbitrage.ui.web.static.js.themes.localStorage') as mock:
            yield mock

    @pytest.fixture
    def mock_document(self):
        with patch('triangular_arbitrage.ui.web.static.js.themes.document') as mock:
            yield mock

    def test_initialize_with_default_theme(self, theme_manager, mock_local_storage):
        mock_local_storage.getItem.return_value = None
        theme_manager.initialize()
        assert theme_manager.currentTheme == 'light'

    def test_initialize_with_saved_theme(self, theme_manager, mock_local_storage):
        mock_local_storage.getItem.return_value = 'dark'
        theme_manager.initialize()
        assert theme_manager.currentTheme == 'dark'

    def test_toggle_theme(self, theme_manager):
        theme_manager.currentTheme = 'light'
        theme_manager.toggleTheme()
        assert theme_manager.currentTheme == 'dark'
        theme_manager.toggleTheme()
        assert theme_manager.currentTheme == 'light'

    def test_apply_theme_updates_html_classes(self, theme_manager, mock_document):
        root = Mock()
        mock_document.documentElement = root
        
        theme_manager.applyTheme('dark')
        
        root.classList.remove.assert_called_with('light', 'dark')
        root.classList.add.assert_called_with('dark')
        assert theme_manager.currentTheme == 'dark'

    def test_apply_theme_saves_preference(self, theme_manager, mock_local_storage):
        theme_manager.applyTheme('dark')
        mock_local_storage.setItem.assert_called_with('theme', 'dark')

    def test_watch_system_theme(self, theme_manager):
        media_query_mock = Mock()
        with patch('triangular_arbitrage.ui.web.static.js.themes.window.matchMedia') as match_media:
            match_media.return_value = media_query_mock
            theme_manager.watchSystemTheme()
            media_query_mock.addListener.assert_called_once()

    def test_observers_notified_on_theme_change(self, theme_manager):
        observer = Mock()
        theme_manager.addObserver(observer)
        theme_manager.applyTheme('dark')
        observer.assert_called_with('dark')

    def test_remove_observer(self, theme_manager):
        observer = Mock()
        theme_manager.addObserver(observer)
        theme_manager.removeObserver(observer)
        theme_manager.applyTheme('dark')
        observer.assert_not_called()

    def test_invalid_theme_ignored(self, theme_manager):
        current_theme = theme_manager.currentTheme
        theme_manager.applyTheme('invalid_theme')
        assert theme_manager.currentTheme == current_theme

    def test_apply_theme_colors(self, theme_manager, mock_document):
        root = Mock()
        mock_document.documentElement = root
        
        colors = {
            'background': '#ffffff',
            'text': {
                'primary': '#000000',
                'secondary': '#666666'
            }
        }
        
        theme_manager.applyThemeColors(colors)
        
        assert root.style.setProperty.call_count == 3
        root.style.setProperty.assert_any_call('--background', '#ffffff')
        root.style.setProperty.assert_any_call('--text-primary', '#000000')
        root.style.setProperty.assert_any_call('--text-secondary', '#666666')

    def test_update_theme_icon(self, theme_manager, mock_document):
        sun_path = Mock()
        moon_path = Mock()
        mock_document.querySelector.side_effect = [sun_path, moon_path]
        
        theme_manager.currentTheme = 'dark'
        theme_manager.updateThemeIcon()
        
        sun_path.classList.add.assert_called_with('hidden')
        moon_path.classList.remove.assert_called_with('hidden')

        theme_manager.currentTheme = 'light'
        theme_manager.updateThemeIcon()
        
        sun_path.classList.remove.assert_called_with('hidden')
        moon_path.classList.add.assert_called_with('hidden')