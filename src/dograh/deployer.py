"""Workflow Deployment Script for Dograh Voice Platform."""

import asyncio
from typing import Dict, Any, Tuple
from config.settings import get_settings
from src.dograh.client import DograhClient
from src.dograh.workflow_builder import (
    build_inbound_booking_workflow,
    build_outbound_qualification_workflow,
    export_workflow_files,
)
from src.utils.logger import get_logger

logger = get_logger("dograh_deployer")


async def deploy_all_workflows(base_webhook_url: str) -> Dict[str, Any]:
    """Deploy both Inbound and Outbound workflows to Dograh platform."""
    client = DograhClient()
    logger.info(f"Building workflows targeting webhook base URL: {base_webhook_url}")

    # 1. Export JSON files to workflows/ directory
    inbound_path, outbound_path = export_workflow_files(base_url=base_webhook_url)
    logger.info(f"Saved visual workflow templates to {inbound_path} and {outbound_path}")

    # 2. Build in-memory definitions
    inbound_wf = build_inbound_booking_workflow(base_webhook_url)
    outbound_wf = build_outbound_qualification_workflow(base_webhook_url)

    # 3. Deploy via API client
    inbound_res = await client.create_workflow(
        name="Inbound Appointment Booking Agent (Alex)",
        workflow_definition=inbound_wf,
    )

    outbound_res = await client.create_workflow(
        name="Outbound Lead Qualification Agent (Jordan)",
        workflow_definition=outbound_wf,
    )

    return {
        "inbound_workflow": inbound_res,
        "outbound_workflow": outbound_res,
        "inbound_file": inbound_path,
        "outbound_file": outbound_path,
    }


if __name__ == "__main__":
    settings = get_settings()
    asyncio.run(deploy_all_workflows(settings.WEBHOOK_BASE_URL))
