import pytest
from playwright.sync_api import Page, expect, RegExp
import json
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))

class TestConfigFlow:
    @pytest.fixture(autouse=True)
    def setup(self, page: Page):
        """Setup para cada teste"""
        # Configurações iniciais
        page.set_viewport_size({"width": 1280, "height": 720})
        
        # Credenciais de teste
        self.test_user = "admin"
        self.test_pass = "admin123"
        
        # Salva page para uso nos testes
        self.page = page

    async def login(self):
        """Helper para realizar login"""
        await self.page.goto("/login")
        await self.page.fill("#username", self.test_user)
        await self.page.fill("#password", self.test_pass)
        await self.page.click("button[type=submit]")
        # Aguarda redirecionamento
        await self.page.wait_for_url("/")

    @pytest.mark.asyncio
    async def test_config_page_access(self):
        """Testa acesso à página de configuração"""
        await self.login()
        
        # Navega para configurações
        await self.page.click("text=Configurações")
        
        # Verifica se chegou na página correta
        await expect(self.page).to_have_url("/config")
        await expect(self.page.locator("h1")).to_contain_text("Configurações do Bot")

    @pytest.mark.asyncio
    async def test_theme_toggle(self):
        """Testa alternância de tema"""
        await self.login()
        await self.page.goto("/config")

        # Verifica tema inicial
        theme = await self.page.evaluate("document.documentElement.classList.contains('dark')")
        initial_is_dark = theme

        # Clica no toggle de tema
        await self.page.click("#theme-toggle")
        
        # Verifica se tema mudou
        theme = await self.page.evaluate("document.documentElement.classList.contains('dark')")
        assert theme != initial_is_dark

    @pytest.mark.asyncio
    async def test_save_config_changes(self):
        """Testa salvamento de configurações"""
        await self.login()
        await self.page.goto("/config")

        # Altera valor de configuração
        await self.page.fill("[data-config='trading.min_profit']", "0.5")
        
        # Clica em salvar
        await self.page.click("#btn-save")
        
        # Aguarda notificação de sucesso
        await self.page.wait_for_selector(".swal2-success")
        
        # Recarrega página e verifica se mudança persistiu
        await self.page.reload()
        value = await self.page.input_value("[data-config='trading.min_profit']")
        assert value == "0.5"

    @pytest.mark.asyncio
    async def test_config_validation(self):
        """Testa validação de campos"""
        await self.login()
        await self.page.goto("/config")

        # Tenta inserir valor inválido
        await self.page.fill("[data-config='trading.min_profit']", "-1")
        
        # Clica em salvar
        await self.page.click("#btn-save")
        
        # Verifica mensagem de erro
        await self.page.wait_for_selector(".swal2-error")
        
        # Verifica se valor não foi salvo
        await self.page.reload()
        value = await self.page.input_value("[data-config='trading.min_profit']")
        assert value != "-1"

    @pytest.mark.asyncio
    async def test_config_export(self):
        """Testa exportação de configurações"""
        await self.login()
        await self.page.goto("/config")

        # Setup para download
        with self.page.expect_download() as download_info:
            # Clica no botão de exportar
            await self.page.click("#btn-export")
        
        download = await download_info.value
        
        # Verifica arquivo baixado
        path = await download.path()
        with open(path) as f:
            config = json.load(f)
            assert "trading" in config
            assert "monitoring" in config

    @pytest.mark.asyncio
    async def test_responsive_layout(self):
        """Testa layout responsivo"""
        await self.login()
        await self.page.goto("/config")

        # Testa diferentes tamanhos de tela
        for size in [(1280, 720), (768, 1024), (375, 812)]:
            await self.page.set_viewport_size({"width": size[0], "height": size[1]})
            
            # Verifica se elementos importantes estão visíveis
            await expect(self.page.locator("h1")).to_be_visible()
            await expect(self.page.locator("#btn-save")).to_be_visible()
            
            # Em telas pequenas, verifica se menu está colapsado
            if size[0] < 768:
                await expect(self.page.locator("nav")).to_have_class(RegExp(r".*collapsed.*"))

    @pytest.mark.asyncio
    async def test_form_interactions(self):
        """Testa interações com formulário"""
        await self.login()
        await self.page.goto("/config")

        # Testa navegação entre tabs
        tabs = ["trading", "monitoring", "rate_limits", "security"]
        for tab in tabs:
            await self.page.click(f"[data-tab='{tab}']")
            await expect(self.page.locator(f"#{tab}-section")).to_be_visible()

        # Testa tooltips
        await self.page.hover("[data-tooltip]")
        await expect(self.page.locator(".tooltip")).to_be_visible()

        # Testa checkboxes
        checkbox = self.page.locator("[data-config='monitoring.notify_on_trade']")
        await checkbox.click()
        await expect(checkbox).to_be_checked()

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Testa tratamento de erros"""
        await self.login()
        await self.page.goto("/config")

        # Simula erro de rede
        await self.page.route("**/api/config/update", lambda route: route.abort())
        
        # Tenta salvar
        await self.page.fill("[data-config='trading.min_profit']", "0.5")
        await self.page.click("#btn-save")
        
        # Verifica mensagem de erro
        await self.page.wait_for_selector(".swal2-error")
        await expect(self.page.locator(".swal2-error")).to_contain_text("Erro ao salvar")

    @pytest.mark.asyncio
    async def test_concurrent_edits(self):
        """Testa edição concorrente"""
        # Abre duas páginas
        context = self.page.context()
        page1 = self.page
        page2 = await context.new_page()

        # Login em ambas
        await self.login()
        await page2.goto("/config")

        # Edita em uma página
        await page1.fill("[data-config='trading.min_profit']", "0.5")
        await page1.click("#btn-save")
        
        # Edita em outra página
        await page2.fill("[data-config='trading.min_profit']", "0.6")
        await page2.click("#btn-save")
        
        # Verifica aviso de conflito
        await page2.wait_for_selector(".swal2-warning")
        await expect(page2.locator(".swal2-warning")).to_contain_text("Conflito")