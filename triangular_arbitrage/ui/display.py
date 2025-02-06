import os
import sys
from typing import Dict, List
from datetime import datetime
import asyncio
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
import logging


class Display:
    def __init__(self):
        """Inicializa o display"""
        self.console = Console()
        self.last_update = None
        self.monitored_pairs = 0
        self.opportunities_checked = 0
        self.logger = logging.getLogger(__name__)

    def clear_screen(self):
        """Limpa a tela"""
        if os.name == 'nt':  # Windows
            os.system('cls')
        else:  # Unix/Linux/MacOS
            os.system('clear')

    def create_header(self) -> Panel:
        """Cria cabeçalho com estatísticas"""
        now = datetime.now().strftime('%H:%M:%S')

        stats = [
            f"[bold cyan]Pares Monitorados:[/] {self.monitored_pairs}",
            f"[bold cyan]Oportunidades:[/] {self.opportunities_checked}",
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

        # Colunas
        table.add_column("Rota", style="cyan", width=30)
        table.add_column("Lucro %", justify="right", width=10)
        table.add_column("Volume", justify="right", width=15)
        table.add_column("Status", style="green", width=10)

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
        """Atualiza display com novas oportunidades"""
        try:
            # Atualiza estatísticas
            self.last_update = datetime.now()
            self.opportunities_checked += 1
            self.monitored_pairs = len(opportunities) if opportunities else 0

            # Limpa a tela
            print("\033[2J\033[H", end="")

            # Cabeçalho
            print("\n🤖 === Monitor de Arbitragem Triangular === 🤖")
            print(f"⏰ Hora: {datetime.now().strftime('%H:%M:%S')}")
            print("=" * 100 + "\n")

            # Cria tabela rica
            table = Table(
                show_header=True,
                header_style="bold white",
                border_style="white",
                show_lines=True,
                width=120,
                box=None,
                padding=(0, 1),
                # Fundo rosa claro para todas as linhas
                row_styles=["on #FFE4E1"]
            )

            # Colunas
            table.add_column("TIPO", style="white", width=15)
            table.add_column("PAR 1", style="white", width=15)
            table.add_column("PAR 2", style="white", width=15)
            table.add_column("PAR 3", style="white", width=15)
            table.add_column("LUCRO (%)", style="white",
                             width=12, justify="right")
            table.add_column("VOLUME", style="white",
                             width=12, justify="right")
            table.add_column("TAXA 1", style="white",
                             width=10, justify="right")
            table.add_column("TAXA 2", style="white",
                             width=10, justify="right")
            table.add_column("TAXA 3", style="white",
                             width=10, justify="right")

            # Adiciona cabeçalho colorido
            table.add_row(
                "TIPO",
                "PAR 1",
                "PAR 2",
                "PAR 3",
                "LUCRO (%)",
                "VOLUME",
                "TAXA 1",
                "TAXA 2",
                "TAXA 3",
                style="on blue"
            )

            if not opportunities:
                table.add_row(
                    "AGUARDANDO",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-"
                )
            else:
                # Ordena por lucro
                sorted_opps = sorted(
                    opportunities,
                    key=lambda x: x.get('profit', 0),
                    reverse=True
                )

                # Adiciona oportunidades
                for opp in sorted_opps[:20]:
                    # Formata os pares
                    pair1 = f"{opp['a_step_from']}/{opp['a_step_to']}"
                    pair2 = f"{opp['b_step_from']}/{opp['b_step_to']}"
                    pair3 = f"{opp['c_step_from']}/{opp['c_step_to']}"

                    # Formata valores
                    profit = f"{opp.get('profit', 0):.3f}"
                    volume = f"{opp.get('volume', 0):.4f} BTC"
                    fees = opp.get('fees', [0.1, 0.1, 0.1])

                    # Adiciona linha
                    table.add_row(
                        opp.get('type', 'TRIANGULAR'),
                        pair1,
                        pair2,
                        pair3,
                        profit,
                        volume,
                        f"{fees[0]:.3f}%",
                        f"{fees[1]:.3f}%",
                        f"{fees[2]:.3f}%"
                    )

            # Imprime tabela
            self.console.print(table)

            # Rodapé
            print("\n❗ Pressione Ctrl+C para encerrar")
            print(f"📊 Pares monitorados: {self.monitored_pairs}")
            print(
                f"🔄 Última atualização: {self.last_update.strftime('%H:%M:%S')}")

            await asyncio.sleep(0.1)

        except Exception as e:
            self.logger.error(f"❌ Erro ao atualizar display: {e}")
            if hasattr(self, 'config') and self.config.get('DEBUG', False):
                self.logger.error(f"🔍 Detalhes: {str(e.__class__.__name__)}")
