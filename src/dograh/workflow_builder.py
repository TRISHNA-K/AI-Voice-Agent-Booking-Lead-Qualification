"""Builder for Dograh visual and programmatic voice workflows."""

import json
from typing import Dict, Any
from config.settings import get_settings
from src.dograh.schemas import (
    WorkflowDefinition,
    WorkflowNode,
    WorkflowEdge,
    NodePosition,
    NodeData,
    ExternalToolSchema,
    ToolParameters,
)
from src.agents.prompts import INBOUND_BOOKING_SYSTEM_PROMPT, OUTBOUND_QUALIFICATION_SYSTEM_PROMPT


def build_inbound_booking_workflow(webhook_base_url: str) -> WorkflowDefinition:
    """
    Construct the complete Dograh graph definition for Inbound Appointment Booking.
    """
    base = webhook_base_url.rstrip("/")

    # Tool definitions
    slot_tool = ExternalToolSchema(
        name="check_available_slots",
        description="Check real-time calendar availability on Cal.com and return open slots.",
        endpoint_url=f"{base}/tools/calcom/check-slots",
        method="POST",
        parameters=ToolParameters(
            properties={
                "date_str": {"type": "string", "description": "Spoken date reference, e.g. 'tomorrow' or 'next Tuesday'"},
                "max_options": {"type": "integer", "description": "Number of alternative slots to return"},
            }
        ),
    )

    book_tool = ExternalToolSchema(
        name="book_appointment",
        description="Book the selected time slot on Cal.com and record booking in CRM.",
        endpoint_url=f"{base}/tools/calcom/book-appointment",
        method="POST",
        parameters=ToolParameters(
            properties={
                "start_time": {"type": "string", "description": "ISO timestamp or spoken slot representation"},
                "name": {"type": "string", "description": "Caller full name"},
                "email": {"type": "string", "description": "Caller email address"},
                "notes": {"type": "string", "description": "Topic or inquiry notes"},
            },
            required=["start_time", "name", "email"],
        ),
    )

    transfer_tool = ExternalToolSchema(
        name="transfer_to_human",
        description="Escalate and transfer call to a human support agent.",
        endpoint_url=f"{base}/tools/telephony/transfer-call",
        method="POST",
        parameters=ToolParameters(
            properties={
                "transfer_reason": {"type": "string", "description": "Reason for human escalation"},
                "caller_name": {"type": "string", "description": "Caller name if known"},
            },
            required=["transfer_reason"],
        ),
    )

    # Nodes
    start_node = WorkflowNode(
        id="node-start-inbound",
        type="startCall",
        position=NodePosition(x=100, y=100),
        data=NodeData(
            name="Inbound Call Entry",
            prompt="Hello! Thank you for calling NovaTech Solutions. My name is Alex. Are you calling to book a new appointment or manage an existing one?",
            wait_for_user_response=True,
        ),
    )

    booking_node = WorkflowNode(
        id="node-agent-booking",
        type="agentNode",
        position=NodePosition(x=100, y=300),
        data=NodeData(
            name="Alex - Booking Specialist",
            prompt=INBOUND_BOOKING_SYSTEM_PROMPT,
            allow_interrupt=True,
            wait_for_user_response=True,
            wait_for_user_response_timeout=8,
            tools=[slot_tool, book_tool, transfer_tool],
        ),
    )

    sync_crm_node = WorkflowNode(
        id="node-webhook-crm-sync",
        type="webhook",
        position=NodePosition(x=100, y=500),
        data=NodeData(
            name="Sync Call & Booking to CRM",
            webhook_url=f"{base}/webhooks/dograh/call-ended",
        ),
    )

    end_node = WorkflowNode(
        id="node-end-inbound",
        type="endCall",
        position=NodePosition(x=100, y=700),
        data=NodeData(name="End Call"),
    )

    # Edges
    edges = [
        WorkflowEdge(
            id="edge-inbound-1",
            source="node-start-inbound",
            target="node-agent-booking",
            condition="Caller responds to initial greeting.",
        ),
        WorkflowEdge(
            id="edge-inbound-2",
            source="node-agent-booking",
            target="node-webhook-crm-sync",
            condition="Appointment is successfully booked or caller has finished their inquiry.",
            transition_speech="Thank you for choosing NovaTech. We look forward to speaking with you then!",
        ),
        WorkflowEdge(
            id="edge-inbound-3",
            source="node-webhook-crm-sync",
            target="node-end-inbound",
            condition="Post-call sync completes.",
        ),
    ]

    return WorkflowDefinition(
        nodes=[start_node, booking_node, sync_crm_node, end_node],
        edges=edges,
    )


def build_outbound_qualification_workflow(webhook_base_url: str) -> WorkflowDefinition:
    """
    Construct the complete Dograh graph definition for Outbound Lead Qualification.
    """
    base = webhook_base_url.rstrip("/")

    # Tools
    slot_tool = ExternalToolSchema(
        name="check_available_slots",
        description="Check live openings for a discovery demo session on Cal.com.",
        endpoint_url=f"{base}/tools/calcom/check-slots",
        method="POST",
        parameters=ToolParameters(
            properties={
                "date_str": {"type": "string", "description": "Date reference"},
            }
        ),
    )

    book_tool = ExternalToolSchema(
        name="book_discovery_call",
        description="Book confirmed discovery walkthrough on Cal.com.",
        endpoint_url=f"{base}/tools/calcom/book-appointment",
        method="POST",
        parameters=ToolParameters(
            properties={
                "start_time": {"type": "string", "description": "Selected slot"},
                "name": {"type": "string", "description": "Prospect name"},
                "email": {"type": "string", "description": "Prospect email"},
                "notes": {"type": "string", "description": "BANT details and requirements"},
            },
            required=["start_time", "name", "email"],
        ),
    )

    qual_tool = ExternalToolSchema(
        name="update_lead_qualification",
        description="Update CRM with BANT qualification scores, lifecycle stage, and notes.",
        endpoint_url=f"{base}/tools/crm/update-qualification",
        method="POST",
        parameters=ToolParameters(
            properties={
                "lead_id": {"type": "string", "description": "CRM Lead ID"},
                "stage": {"type": "string", "description": "SQL, MQL, or Disqualified"},
                "score": {"type": "integer", "description": "BANT score 0-100"},
                "bant_data": {"type": "object", "description": "Extracted BANT fields"},
                "summary": {"type": "string", "description": "Summary rationale"},
            },
            required=["lead_id", "stage", "score", "bant_data"],
        ),
    )

    start_node = WorkflowNode(
        id="node-start-outbound",
        type="startCall",
        position=NodePosition(x=150, y=100),
        data=NodeData(
            name="Outbound Opening",
            prompt="Hi there, this is Jordan calling from NovaTech Solutions regarding your inquiry on our Voice AI agents. Did I catch you at an okay time for a quick chat?",
            wait_for_user_response=True,
        ),
    )

    qual_agent_node = WorkflowNode(
        id="node-agent-qualifier",
        type="agentNode",
        position=NodePosition(x=150, y=300),
        data=NodeData(
            name="Jordan - Lead Qualifier",
            prompt=OUTBOUND_QUALIFICATION_SYSTEM_PROMPT,
            allow_interrupt=True,
            wait_for_user_response=True,
            wait_for_user_response_timeout=8,
            tools=[slot_tool, book_tool, qual_tool],
        ),
    )

    webhook_node = WorkflowNode(
        id="node-webhook-outbound-sync",
        type="webhook",
        position=NodePosition(x=150, y=500),
        data=NodeData(
            name="CRM Call & Transcript Sync",
            webhook_url=f"{base}/webhooks/dograh/call-ended",
        ),
    )

    end_node = WorkflowNode(
        id="node-end-outbound",
        type="endCall",
        position=NodePosition(x=150, y=700),
        data=NodeData(name="End Outbound Call"),
    )

    edges = [
        WorkflowEdge(
            id="edge-outbound-1",
            source="node-start-outbound",
            target="node-agent-qualifier",
            condition="Prospect answers call and is open to chatting.",
        ),
        WorkflowEdge(
            id="edge-outbound-2",
            source="node-agent-qualifier",
            target="node-webhook-outbound-sync",
            condition="BANT qualification is complete and next step is set.",
            transition_speech="Thank you so much for your time today. Have a great day!",
        ),
        WorkflowEdge(
            id="edge-outbound-3",
            source="node-webhook-outbound-sync",
            target="node-end-outbound",
            condition="Sync completes.",
        ),
    ]

    return WorkflowDefinition(
        nodes=[start_node, qual_agent_node, webhook_node, end_node],
        edges=edges,
    )


def export_workflow_files(output_dir: str = "workflows", base_url: str = "http://localhost:8000"):
    """Export visual-compatible JSON files for Dograh dashboard import."""
    import os
    os.makedirs(output_dir, exist_ok=True)

    inbound = build_inbound_booking_workflow(base_url)
    inbound_path = os.path.join(output_dir, "inbound_booking_workflow.json")
    with open(inbound_path, "w", encoding="utf-8") as f:
        json.dump(inbound.model_dump(), f, indent=2)

    outbound = build_outbound_qualification_workflow(base_url)
    outbound_path = os.path.join(output_dir, "outbound_qualification_workflow.json")
    with open(outbound_path, "w", encoding="utf-8") as f:
        json.dump(outbound.model_dump(), f, indent=2)

    return inbound_path, outbound_path
