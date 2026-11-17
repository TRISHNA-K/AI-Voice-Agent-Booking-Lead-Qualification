"""Interactive Voice Agent Simulator.

Allows testing inbound and outbound conversation flows in terminal
with live tool execution, BANT scoring, and CRM updates.
"""

import asyncio
from typing import List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.agents.inbound_booking_agent import InboundBookingAgent
from src.agents.outbound_lead_agent import OutboundLeadAgent
from src.tools.crm_tool import get_crm_adapter

console = Console()


class VoiceSimulator:
    """Terminal-based Voice Conversation Simulator."""

    def __init__(self):
        self.crm = get_crm_adapter()

    async def run_inbound_simulation(self, script_utterances: Optional[List[str]] = None):
        """Run simulated inbound call."""
        console.print(Panel("[bold green]📞 INCOMING CALL CONNECTED[/bold green]\nAgent: Alex (NovaTech Inbound Booking)", border_style="green"))
        agent = InboundBookingAgent()

        # Initial Agent Welcome
        welcome = (
            "Hello! Thank you for calling NovaTech Solutions. My name is Alex. "
            "Are you calling to book a new appointment or manage an existing one?"
        )
        console.print(f"[bold cyan]Alex (Voice Agent):[/bold cyan] {welcome}\n")

        # Default script for automated showcase if none provided
        dialogue = script_utterances or [
            "Hi, I'd like to book a consultation for next Tuesday.",
            "My name is Michael Scott and my email is michael.scott@dunder.example. The 2:00 PM slot works great.",
            "That's all, thank you so much!",
        ]

        for utterance in dialogue:
            console.print(f"[bold yellow]Caller (User):[/bold yellow] {utterance}")
            res = await agent.process_turn(utterance)

            # Print tool calls if any
            if res.get("tool_calls"):
                for tc in res["tool_calls"]:
                    tool_name = tc.get("tool")
                    tool_res = tc.get("result")
                    console.print(f"  [bold magenta]⚡ Tool Executed:[/bold magenta] [italic]{tool_name}[/italic]")
                    if tool_name == "book_appointment":
                        console.print(f"    [dim]Booking ID: {tool_res.get('booking_id')} | Time: {tool_res.get('formatted_time')}[/dim]")

            console.print(f"[bold cyan]Alex (Voice Agent):[/bold cyan] {res['speech']}\n")

        console.print(Panel("[bold red]📴 CALL ENDED[/bold red]", border_style="red"))

    async def run_outbound_simulation(self, script_utterances: Optional[List[str]] = None):
        """Run simulated outbound qualification call."""
        lead_context = {
            "customer_name": "David Wallace",
            "company": "CFO Advisory Partners",
            "phone": "+15554321098",
            "interest": "Voice AI Booking & Scheduling",
            "lead_id": "lead_outbound_001",
        }

        console.print(Panel(
            f"[bold blue]📲 DISPATCHING OUTBOUND CALL[/bold blue]\n"
            f"Target: {lead_context['customer_name']} ({lead_context['company']})\n"
            f"Agent: Jordan (Lead Qualification Specialist)",
            border_style="blue"
        ))

        agent = OutboundLeadAgent(lead_context=lead_context)
        greeting = agent.get_initial_greeting()
        console.print(f"[bold cyan]Jordan (Voice Agent):[/bold cyan] {greeting}\n")

        dialogue = script_utterances or [
            "Yes, I have two minutes. What's this about?",
            "Our main problem is our sales team is missing leads after hours and we lose high-value consultations.",
            "I'm the Managing Partner, so I make the final purchasing decision.",
            "We want to deploy this within the next 30 days before our next marketing push.",
            "Yes, we've set aside a $25,000 budget for automation software.",
            "Tomorrow afternoon works well for me, let's do 2:00 PM.",
        ]

        for utterance in dialogue:
            console.print(f"[bold yellow]David Wallace (Prospect):[/bold yellow] {utterance}")
            res = await agent.process_turn(utterance)

            if res.get("tool_calls"):
                for tc in res["tool_calls"]:
                    tool_name = tc.get("tool")
                    console.print(f"  [bold magenta]⚡ Tool Executed:[/bold magenta] [italic]{tool_name}[/italic]")

            if res.get("score") is not None:
                console.print(f"  [bold green]📊 Lead Qualification Score: {res['score']}/100[/bold green]")

            console.print(f"[bold cyan]Jordan (Voice Agent):[/bold cyan] {res['speech']}\n")

        console.print(Panel("[bold red]📴 CALL COMPLETED[/bold red]", border_style="red"))
