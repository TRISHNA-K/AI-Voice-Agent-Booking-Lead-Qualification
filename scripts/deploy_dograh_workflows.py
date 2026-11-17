"""CLI Script to generate and deploy Dograh Workflows."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import get_settings
from src.dograh.deployer import deploy_all_workflows
from rich.console import Console
from rich.panel import Panel

console = Console()


async def main():
    settings = get_settings()
    console.print(Panel(
        f"[bold cyan]Deploying Dograh Voice Workflows[/bold cyan]\n"
        f"Dograh Server: [dim]{settings.DOGRAH_API_URL}[/dim]\n"
        f"Webhook Base: [dim]{settings.WEBHOOK_BASE_URL}[/dim]",
        border_style="cyan"
    ))

    result = await deploy_all_workflows(settings.WEBHOOK_BASE_URL)

    console.print("\n[bold green]✅ Deployment Complete![/bold green]")
    console.print(f"📁 Inbound Blueprint Saved: [bold]{result['inbound_file']}[/bold]")
    console.print(f"📁 Outbound Blueprint Saved: [bold]{result['outbound_file']}[/bold]")
    console.print(f"🆔 Inbound Workflow ID: [bold]{result['inbound_workflow'].get('id')}[/bold]")
    console.print(f"🆔 Outbound Workflow ID: [bold]{result['outbound_workflow'].get('id')}[/bold]\n")


if __name__ == "__main__":
    asyncio.run(main())
