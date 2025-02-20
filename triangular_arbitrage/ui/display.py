"""
Display module for terminal visualization
"""
from rich.console import Console
from rich.table import Table
from rich.live import Live
from typing import Dict, List
from datetime import datetime
import logging

class Display:
    def __init__(self):
        """Inicializa o display com uma única tabela"""
        # Configurações básicas
        self.console = Console()
        self.last_update = None
        self.opportunities = []
        self.logger = logging.getLogger(__name__)
        
        # Configuração da tabela de oportunidades
        self.table = self._setup_table()
        
        # Inicia display live
        self.live = Live(
            self.table,
            console=self.console,
            refresh_per_second=2,
            vertical_overflow="visible"
        )
        self.live.start()
        
    def _setup_table(self) -> Table:
        """Configura a tabela única de oportunidades"""
        table = Table(
            title="💰 Oportunidades de Arbitragem (Dados Reais)",
            show_header=True,
            header_style="bold white",
            show_lines=True,
            expand=True,
            title_style="bold magenta",
            border_style="blue",
            box=None  # Remove bordas extras
        )

        # Adiciona colunas conforme estrutura definida
        table.add_column("Rota de Arbitragem", style="cyan", width=40)
        table.add_column("Profit Esperado", style="green", justify="right", width=12)
        table.add_column("Profit Real", style="yellow", justify="right", width=12)
        table.add_column("Slippage", style="red", justify="right", width=10)
        table.add_column("Tempo Exec.", style="blue", justify="right", width=12)
        table.add_column("Liquidez", style="magenta", justify="right", width=15)
        table.add_column("Risco", style="red", justify="right", width=8)
        table.add_column("Spread", style="yellow", justify="right", width=10)
        table.add_column("Volatilidade", style="magenta", justify="right", width=12)
        table.add_column("Confiança", style="green", justify="right", width=10)

        return table
        
        # Configura colunas com larguras fixas
        self.table.add_column("Rota de Arbitragem", style="cyan", width=40)
        self.table.add_column("Profit Esperado", style="green", justify="right", width=12)
        self.table.add_column("Profit Real", style="yellow", justify="right", width=12)
        self.table.add_column("Slippage", style="red", justify="right", width=10)
        self.table.add_column("Tempo Exec.", style="blue", justify="right", width=12)
        self.table.add_column("Liquidez", style="magenta", justify="right", width=15)
        self.table.add_column("Risco", style="red", justify="right", width=8)
        self.table.add_column("Spread", style="yellow", justify="right", width=10)
        self.table.add_column("Volatilidade", style="magenta", justify="right", width=12)
        self.table.add_column("Confiança", style="green", justify="right", width=10)
        
        # Inicia display live
        self.live = Live(
            self.table,
            refresh_per_second=2,
            console=self.console,
            vertical_overflow="visible",
            auto_refresh=False  # Controle manual do refresh
        )
        self.live.start()

    def _format_opportunity(self, opp: Dict) -> Dict:
        """Formata dados da oportunidade para exibição"""
        try:
            metrics = opp.get('market_metrics', {})
            profit = float(opp.get('profit', 0))
            slippage = metrics.get('slippage', 0)
            execution_time = metrics.get('execution_time', 0)
            liquidity = metrics.get('liquidity', 0)
            risk = metrics.get('risk_score', 0)
            spread = metrics.get('spread', 0) * 100
            volatility = metrics.get('volatility', 0)
            confidence = metrics.get('confidence_score', 0)

            # Indicadores visuais
            profit_indicator = "💰" if profit > 1.0 else "✨" if profit > 0.5 else "📊"
            risk_indicator = "⚠️" if risk > 7 else "📊" if risk > 5 else "✅"
            liquidity_indicator = "💧" if liquidity > 1000 else "💦"

            return {
                'route': f"[cyan]{opp.get('path', 'N/A')}[/]",
                'profit_expected': f"[{'green' if profit > 1.0 else 'yellow'}]{profit_indicator} {profit:>6.3f}%[/]",
                'profit_real': f"[{'green' if profit-slippage > 0.5 else 'yellow'}]{(profit-slippage):>6.3f}%[/]",
                'slippage': f"[red]{slippage:>6.3f}%[/]",
                'execution_time': f"[blue]⚡{execution_time:>6.2f}s[/]",
                'liquidity': f"[magenta]{liquidity_indicator}${liquidity:>9,.2f}[/]",
                'risk': f"[red]{risk_indicator}{risk:>3.1f}/10[/]",
                'spread': f"[yellow]📊{spread:>6.3f}%[/]",
                'volatility': f"[magenta]📈{volatility:>6.2f}%[/]",
                'confidence': f"[green]🎯{confidence:>3.0f}%[/]"
            }
        except Exception as e:
            self.logger.error(f"Erro ao formatar oportunidade: {e}")
            return {}

    async def update_opportunities(self, opportunities: List[Dict]):
        """Atualiza dados das oportunidades na tabela"""
        try:
            # Limpa tabela atual
            self.table.rows.clear()
            self.opportunities = opportunities

            # Mensagem quando não há dados
            if not opportunities:
                self.table.add_row(
                    "[yellow]Aguardando oportunidades de arbitragem...[/]",
                    *["" for _ in range(9)]
                )
                self.live.refresh()
                return

            # Adiciona oportunidades ordenadas
            sorted_opps = sorted(
                opportunities,
                key=lambda x: float(x.get('profit', 0)),
                reverse=True
            )[:10]  # Top 10

            for opp in sorted_opps:
                formatted = self._format_opportunity(opp)
                if formatted:
                    self.table.add_row(
                        formatted['route'],
                        formatted['profit_expected'],
                        formatted['profit_real'],
                        formatted['slippage'],
                        formatted['execution_time'],
                        formatted['liquidity'],
                        formatted['risk'],
                        formatted['spread'],
                        formatted['volatility'],
                        formatted['confidence']
                    )

            # Atualiza timestamp e display
            self.last_update = datetime.now()
            self.live.refresh()

        except Exception as e:
            self.logger.error(f"Erro ao atualizar oportunidades: {e}")
            self.logger.debug("Stack trace:", exc_info=True)

    def stop(self):
        """Para o display"""
        try:
            if hasattr(self, 'live'):
                self.live.stop()
        except Exception as e:
            self.logger.error(f"Erro ao parar display: {e}")
