"""Pydantic schemas for Dograh AI Workflow Definitions and Calls."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class NodePosition(BaseModel):
    """2D canvas coordinates for visual workflow builder."""
    x: float
    y: float


class ToolParameterProperty(BaseModel):
    type: str
    description: Optional[str] = None
    enum: Optional[List[str]] = None


class ToolParameters(BaseModel):
    type: str = "object"
    properties: Dict[str, Any] = Field(default_factory=dict)
    required: Optional[List[str]] = None


class ExternalToolSchema(BaseModel):
    """External HTTP API tool registered with an agent node in Dograh."""
    name: str
    description: str
    endpoint_url: str
    method: str = "POST"
    parameters: ToolParameters
    headers: Optional[Dict[str, str]] = None


class NodeData(BaseModel):
    """Node configuration parameters."""
    name: str
    prompt: Optional[str] = None
    allow_interrupt: bool = True
    wait_for_user_response: bool = True
    wait_for_user_response_timeout: int = 10
    tools: Optional[List[ExternalToolSchema]] = None
    transfer_phone_number: Optional[str] = None
    webhook_url: Optional[str] = None


class WorkflowNode(BaseModel):
    """Single node within a Dograh graph."""
    id: str
    type: str  # 'startCall', 'agentNode', 'globalNode', 'webhook', 'endCall', 'transferCall'
    position: NodePosition
    data: NodeData


class WorkflowEdge(BaseModel):
    """Directed edge connecting nodes with conditional transitions."""
    id: str
    source: str
    target: str
    condition: Optional[str] = None
    transition_speech: Optional[str] = None


class WorkflowDefinition(BaseModel):
    """Top-level Dograh Workflow Graph structure."""
    nodes: List[WorkflowNode]
    edges: List[WorkflowEdge]


class CallDispatchPayload(BaseModel):
    """Payload to initiate outbound telephony call."""
    workflow_id: str
    phone_number: str
    initial_context: Dict[str, Any] = Field(default_factory=dict)


class CallDispatchResponse(BaseModel):
    id: str
    status: str
    phone_number: str
    created_at: str
