"""Run Inbound Appointment Booking Voice Simulation."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.simulator.voice_simulator import VoiceSimulator
from src.agents.inbound_booking_agent import InboundBookingAgent
from rich.console import Console

console = Console()


async def interactive_inbound():
    """Live interactive terminal call with the inbound agent."""
    console.print("[bold green]📞 INBOUND CALL STARTED - Type your responses like speaking on the phone. Type 'exit' to hang up.[/bold green]\n")
    agent = InboundBookingAgent()

    welcome = (
        "Hello! Thank you for calling NovaTech Solutions. My name is Alex. "
        "Are you calling to book a new appointment or manage an existing one?"
    )
    console.print(f"[bold cyan]Alex (Voice Agent):[/bold cyan] {welcome}\n")

    while True:
        try:
            user_input = input("You (Caller): ").strip()
            if not user_input or user_input.lower() in ("exit", "quit", "hang up"):
                console.print("\n[bold red]📴 Call ended by caller.[/bold red]")
                break

            res = await agent.process_turn(user_input)

            if res.get("tool_calls"):
                for tc in res["tool_calls"]:
                    console.print(f"  [bold magenta]⚡ Tool Executed:[/bold magenta] [italic]{tc.get('tool')}[/italic]")

            console.print(f"[bold cyan]Alex (Voice Agent):[/bold cyan] {res['speech']}\n")

            if res.get("action") in ("transfer", "cancelled", "booked"):
                if res.get("action") == "booked":
                    console.print("[bold green]✨ Appointment successfully booked![/bold green]\n")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold red]📴 Call disconnected.[/bold red]")
            break


async def main():
    sim = VoiceSimulator()
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        await interactive_inbound()
    else:
        console.print("[dim]Tip: Pass '--interactive' to chat with the voice agent manually.[/dim]\n")
        await sim.run_inbound_simulation()


if __name__ == "__main__":
    asyncio.run(main())
