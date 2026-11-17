"""Run Outbound Lead Qualification Voice Simulation."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.simulator.voice_simulator import VoiceSimulator
from src.agents.outbound_lead_agent import OutboundLeadAgent
from rich.console import Console

console = Console()


async def interactive_outbound():
    """Live interactive outbound call with Jordan (Lead Qualifier)."""
    lead_context = {
        "customer_name": "Sarah Jenkins",
        "company": "Venture Growth Media",
        "phone": "+15556781234",
        "interest": "Voice AI Agent for CRM Follow-up",
        "lead_id": "lead_interactive_99",
    }
    console.print(f"[bold blue]📲 OUTBOUND CALL CONNECTED to {lead_context['customer_name']} ({lead_context['company']})[/bold blue]\n")
    agent = OutboundLeadAgent(lead_context=lead_context)

    greeting = agent.get_initial_greeting()
    console.print(f"[bold cyan]Jordan (Voice Agent):[/bold cyan] {greeting}\n")

    while True:
        try:
            user_input = input("You (Prospect): ").strip()
            if not user_input or user_input.lower() in ("exit", "quit", "hang up"):
                console.print("\n[bold red]📴 Call ended.[/bold red]")
                break

            res = await agent.process_turn(user_input)

            if res.get("tool_calls"):
                for tc in res["tool_calls"]:
                    console.print(f"  [bold magenta]⚡ Tool Executed:[/bold magenta] [italic]{tc.get('tool')}[/italic]")

            if res.get("score") is not None:
                console.print(f"  [bold green]📊 BANT Score: {res['score']}/100[/bold green]")

            console.print(f"[bold cyan]Jordan (Voice Agent):[/bold cyan] {res['speech']}\n")

            if res.get("action") in ("reschedule", "disqualified", "booking_completed", "ended"):
                break
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold red]📴 Call disconnected.[/bold red]")
            break


async def main():
    sim = VoiceSimulator()
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        await interactive_outbound()
    else:
        console.print("[dim]Tip: Pass '--interactive' to chat with the voice agent manually.[/dim]\n")
        await sim.run_outbound_simulation()


if __name__ == "__main__":
    asyncio.run(main())
