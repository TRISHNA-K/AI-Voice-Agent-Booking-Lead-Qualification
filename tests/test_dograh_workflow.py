"""Unit tests for Dograh Workflow schemas and builder."""

import json
import pytest
from src.dograh.workflow_builder import (
    build_inbound_booking_workflow,
    build_outbound_qualification_workflow,
    export_workflow_files,
)
from src.dograh.schemas import WorkflowDefinition


def test_inbound_workflow_schema():
    wf = build_inbound_booking_workflow(webhook_base_url="https://api.novatech.example")
    assert isinstance(wf, WorkflowDefinition)
    assert len(wf.nodes) >= 4
    assert len(wf.edges) >= 3

    # Verify start node
    start = next(n for n in wf.nodes if n.type == "startCall")
    assert start.data.wait_for_user_response is True

    # Verify agent node has tools
    agent_node = next(n for n in wf.nodes if n.type == "agentNode")
    assert agent_node.data.tools is not None
    tool_names = [t.name for t in agent_node.data.tools]
    assert "check_available_slots" in tool_names
    assert "book_appointment" in tool_names


def test_outbound_workflow_schema():
    wf = build_outbound_qualification_workflow(webhook_base_url="https://api.novatech.example")
    assert isinstance(wf, WorkflowDefinition)

    # Check edges connect valid node IDs
    node_ids = {n.id for n in wf.nodes}
    for edge in wf.edges:
        assert edge.source in node_ids
        assert edge.target in node_ids


def test_export_workflow_files(tmp_path):
    inbound_file, outbound_file = export_workflow_files(output_dir=str(tmp_path))
    with open(inbound_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert "nodes" in data
        assert "edges" in data

    with open(outbound_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert "nodes" in data
        assert "edges" in data
