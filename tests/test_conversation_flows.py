"""End-to-End Conversation Flow Tests."""

import asyncio
from src.agents.inbound_booking_agent import InboundBookingAgent
from src.agents.outbound_lead_agent import OutboundLeadAgent


def test_inbound_booking_conversation_flow():
    agent = InboundBookingAgent()

    # Turn 1: Greeting
    turn1 = asyncio.run(agent.process_turn("Hello, good morning!"))
    assert "NovaTech" in turn1["speech"] or "Alex" in turn1["speech"]

    # Turn 2: Scheduling request
    turn2 = asyncio.run(agent.process_turn("I need to book a consultation for next Tuesday."))
    assert len(turn2["tool_calls"]) > 0
    assert turn2["tool_calls"][0]["tool"] == "check_available_slots"
    assert "openings" in turn2["speech"] or "opening" in turn2["speech"] or "available" in turn2["speech"]

    # Turn 3: Provide time and contact info
    turn3 = asyncio.run(agent.process_turn("My name is John Doe and my email is john.doe@example.com. 2pm works."))
    assert len(turn3["tool_calls"]) > 0
    assert turn3["tool_calls"][0]["tool"] == "book_appointment"
    assert "booked" in turn3["speech"].lower() or "confirmed" in turn3["speech"].lower()


def test_inbound_human_transfer_flow():
    agent = InboundBookingAgent()
    turn = asyncio.run(agent.process_turn("I want to speak with a human representative please."))
    assert turn["action"] == "transfer"
    assert "transfer" in turn["speech"].lower() or "specialist" in turn["speech"].lower()


def test_outbound_lead_qualification_flow():
    lead_context = {
        "customer_name": "Tony Stark",
        "company": "Stark Industries",
        "phone": "+15553000000",
        "interest": "Voice AI",
        "lead_id": "lead_stark_01",
    }
    agent = OutboundLeadAgent(lead_context=lead_context)

    # Handshake
    turn1 = asyncio.run(agent.process_turn("Yes, I have two minutes. Tell me more."))
    assert turn1["action"] == "ask_need"

    # Need
    turn2 = asyncio.run(agent.process_turn("We are overwhelmed with missed customer appointment calls every evening."))
    assert turn2["action"] == "ask_authority"

    # Authority
    turn3 = asyncio.run(agent.process_turn("I am the CEO and sole decision maker."))
    assert turn3["action"] == "ask_timeline"

    # Timeline
    turn4 = asyncio.run(agent.process_turn("We need this deployed immediately within the next two weeks."))
    assert turn4["action"] == "ask_budget"

    # Budget
    turn5 = asyncio.run(agent.process_turn("Yes, we have an approved $50,000 budget for this."))
    assert turn5["action"] == "offer_booking"
    assert turn5["score"] >= 70
    assert "demo" in turn5["speech"].lower() or "walkthrough" in turn5["speech"].lower()
