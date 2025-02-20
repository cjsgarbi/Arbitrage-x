import os
import sys
import time
from typing import Dict, List
from datetime import datetime
import asyncio
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from rich.live import Live
import logging


class Display:
    def __init__(self):
        """Inicializa o display"""
        self.console = Console()
        self.last_update = None
        self.opportunities = []
        self.pairs_monitored = 0
        self.logger = logging.getLogger(__name__)
        self.live = Live()
        self.table = Table()

    def clear_screen(self):
        """Limpa a tela do console"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def create_header(self) -> Panel:
        """Cria cabeçalho com estatísticas"""
        now = datetime.now().strftime('%H:%M:%S')

        stats = [
            f"[bold cyan]Pares Monitorados:[/] {self.pairs_monitored}",
            f"[bold cyan]Oportunidades:[/] {len(self.opportunities)}",
        ]

        if self.last_update:
            stats.append(
                f"[bold cyan]Última Atualização:[/] {(datetime.now() - self.last_update).total_seconds():.1f}s atrás"
            )

        header_text = Text.assemble(
            ("Monitor de Arbitragem Triangular\n", "bold white"),
            (now + "\n\n", "bold green"),
            *[f"{stat}\n" for stat in stats]
        )

        return Panel(
            header_text,
            border_style="blue",
            padding=(1, 2),
            title="🤖 Bot de Arbitragem",
            subtitle="v1.0"
        )

    def create_opportunities_table(self, opportunities: List[Dict]) -> Table:
        """Cria tabela de oportunidades"""
        table = Table(
            show_header=True,
            header_style="bold magenta",
            border_style="bright_blue",
            title="💰 Oportunidades de Arbitragem",
            caption="Atualizado em tempo real"
        )

        # Colunas com todas as métricas
        table.add_column("Rota de Arbitragem", style="cyan", width=35)
        table.add_column("Profit Esperado", justify="right", style="green", width=15)
        table.add_column("Profit Real", justify="right", style="yellow", width=12)
        table.add_column("Slippage", justify="right", style="red", width=10)
        table.add_column("Tempo Exec.", justify="right", style="blue", width=12)
        table.add_column("Liquidez", justify="right", style="magenta", width=12)
        table.add_column("Risco", justify="right", style="red", width=8)
        table.add_column("Spread", justify="right", style="yellow", width=10)
        table.add_column("Volatilidade", justify="right", style="magenta", width=12)
        table.add_column("Confiança", justify="right", style="green", width=10)

        if not opportunities:
            table.add_row(
                "[yellow]Aguardando oportunidades...[/]",
                "", "", ""
            )
            return table

        # Ordena por lucro
        sorted_opps = sorted(
            opportunities,
            key=lambda x: x['profit'],
            reverse=True
        )

        # Mostra top oportunidades
        for opp in sorted_opps[:20]:  # Limita a 20 oportunidades
            route = f"{opp['a_step_from']} → {opp['b_step_from']} → {opp['c_step_from']}"
            profit = f"{opp['profit']:.3f}%"
            volume = f"${opp['volume']:.2f}"

            # Define cor baseada no lucro
            if opp['profit'] > 1.0:
                profit_style = "green"
            elif opp['profit'] > 0.5:
                profit_style = "yellow"
            else:
                profit_style = "white"

            table.add_row(
                route,
                f"[{profit_style}]{profit}[/]",
                volume,
                "✅" if opp['profit'] > 0.5 else "⏳"
            )

        return table

    def create_layout(self) -> Layout:
        """Cria layout da interface"""
        layout = Layout()

        # Divide em seções
        layout.split(
            Layout(name="header", size=10),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )

        # Divide o corpo em duas colunas
        layout["body"].split_row(
            Layout(name="opportunities", ratio=2),
            Layout(name="stats", ratio=1)
        )

        return layout

    async def update_arbitrage_opportunities(self, opportunities: List[Dict]):
        """Atualiza tabela com oportunidades de arbitragem"""
        # Limpa linhas existentes
        self.table.rows.clear()

        # Ordena por lucro
        sorted_opps = sorted(
            opportunities, key=lambda x: x['profit'], reverse=True)

        # Mostra top 10 oportunidades
        for opp in sorted_opps[:10]:
            # Formata rota
            route = f"{opp['a_step_from']}->{opp['b_step_from']}->{opp['c_step_from']}"

            # Formata timestamp
            ts = datetime.fromisoformat(opp['timestamp']).strftime("%H:%M:%S")

            # Adiciona linha na tabela
            self.table.add_row(
                "BUY_SELL_SELL",
                opp['a_step_from'] + "/" + opp['a_step_to'],
                opp['b_step_from'] + "/" + opp['b_step_to'],
                opp['c_step_from'] + "/" + opp['c_step_to'],
                f"{opp['profit']:.2f}",
                f"{opp['a_volume']:.4f}",
                f"{opp.get('avg_spread', 0):.2f}",
                f"{opp.get('score', 0):.0f}",
                ts
            )

        # Força atualização da tabela
        self.live.refresh()

    def stop(self):
        """Para exibição da tabela"""
        self.live.stop()
