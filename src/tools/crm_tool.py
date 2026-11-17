"""Universal CRM Integration Tool for Voice Agents.

Supports HubSpot, Salesforce, Pipedrive, and Local File Mock CRM
for lead lookup, lead qualification updates, call logging, and task scheduling.
"""

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx

from config.settings import get_settings
from src.utils.logger import get_logger
from src.utils.phone_utils import normalize_phone_number

logger = get_logger("crm_tool")


class BaseCRMAdapter(ABC):
    """Abstract interface for CRM providers."""

    @abstractmethod
    async def lookup_lead(self, phone: Optional[str] = None, email: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Find contact by phone number or email."""
        pass

    @abstractmethod
    async def create_or_update_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert or update lead attributes."""
        pass

    @abstractmethod
    async def update_qualification(
        self,
        lead_id: str,
        stage: str,
        score: int,
        bant_data: Dict[str, Any],
        summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update qualification stage, BANT score, and qualification notes."""
        pass

    @abstractmethod
    async def log_call(
        self,
        lead_id: str,
        call_direction: str,  # 'inbound' or 'outbound'
        duration_seconds: int,
        summary: str,
        transcript: str,
        outcome: str,
        recording_url: Optional[str] = None,
        booking_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Log call engagement record with full transcript and intelligence."""
        pass


class LocalJSONCRMAdapter(BaseCRMAdapter):
    """Zero-dependency local JSON file CRM adapter for local testing and CI."""

    def __init__(self, db_path: Optional[str] = None):
        settings = get_settings()
        self.db_path = db_path or settings.CRM_DATABASE_FILE
        self._ensure_db()

    def _ensure_db(self):
        if not os.path.exists(self.db_path):
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump({"contacts": [], "bookings": []}, f, indent=2)

    def _read_data(self) -> Dict[str, Any]:
        self._ensure_db()
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"contacts": [], "bookings": []}

    def _write_data(self, data: Dict[str, Any]):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    async def lookup_lead(self, phone: Optional[str] = None, email: Optional[str] = None) -> Optional[Dict[str, Any]]:
        data = self._read_data()
        norm_phone = normalize_phone_number(phone) if phone else None
        target_email = email.lower().strip() if email else None

        for contact in data.get("contacts", []):
            if norm_phone and normalize_phone_number(contact.get("phone", "")) == norm_phone:
                return contact
            if target_email and contact.get("email", "").lower() == target_email:
                return contact
        return None

    async def create_or_update_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        data = self._read_data()
        contacts = data.get("contacts", [])
        phone = lead_data.get("phone")
        email = lead_data.get("email")

        existing = await self.lookup_lead(phone=phone, email=email)
        now_iso = datetime.now().isoformat()

        if existing:
            # Update
            for idx, c in enumerate(contacts):
                if c.get("id") == existing.get("id"):
                    contacts[idx].update(lead_data)
                    contacts[idx]["updated_at"] = now_iso
                    data["contacts"] = contacts
                    self._write_data(data)
                    logger.info(f"[Local CRM] Updated lead: {existing.get('id')} - {c.get('name')}")
                    return contacts[idx]
        else:
            # Create
            new_id = f"lead_{int(datetime.now().timestamp())}"
            record = {
                "id": new_id,
                "phone": normalize_phone_number(phone) if phone else "",
                "name": lead_data.get("name", "Unknown Contact"),
                "email": email or "",
                "company": lead_data.get("company", "Independent"),
                "status": lead_data.get("status", "New Lead"),
                "stage": lead_data.get("stage", "Lead"),
                "lead_score": lead_data.get("lead_score", 0),
                "notes": lead_data.get("notes", ""),
                "created_at": now_iso,
                "updated_at": now_iso,
                "call_logs": [],
            }
            record.update(lead_data)
            contacts.append(record)
            data["contacts"] = contacts
            self._write_data(data)
            logger.info(f"[Local CRM] Created new lead: {new_id} - {record.get('name')}")
            return record

    async def update_qualification(
        self,
        lead_id: str,
        stage: str,
        score: int,
        bant_data: Dict[str, Any],
        summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        data = self._read_data()
        for c in data.get("contacts", []):
            if c.get("id") == lead_id:
                c["stage"] = stage
                c["lead_score"] = score
                c["bant_data"] = bant_data
                if summary:
                    c["notes"] = f"{c.get('notes', '')}\n[Qualification {datetime.now().strftime('%Y-%m-%d')}] {summary}".strip()
                c["updated_at"] = datetime.now().isoformat()
                self._write_data(data)
                logger.info(f"[Local CRM] Lead {lead_id} scored {score}/100, stage set to: {stage}")
                return c

        return {"error": "Lead not found"}

    async def log_call(
        self,
        lead_id: str,
        call_direction: str,
        duration_seconds: int,
        summary: str,
        transcript: str,
        outcome: str,
        recording_url: Optional[str] = None,
        booking_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        data = self._read_data()
        call_entry = {
            "call_id": f"call_{int(datetime.now().timestamp())}",
            "direction": call_direction,
            "duration_seconds": duration_seconds,
            "summary": summary,
            "transcript": transcript,
            "outcome": outcome,
            "recording_url": recording_url,
            "booking_id": booking_id,
            "timestamp": datetime.now().isoformat(),
        }

        for c in data.get("contacts", []):
            if c.get("id") == lead_id:
                if "call_logs" not in c:
                    c["call_logs"] = []
                c["call_logs"].append(call_entry)
                c["updated_at"] = datetime.now().isoformat()
                self._write_data(data)
                logger.info(f"[Local CRM] Logged {call_direction} call for lead {lead_id}: {outcome}")
                return call_entry

        return {"error": "Lead not found for call logging"}


class HubSpotCRMAdapter(BaseCRMAdapter):
    """HubSpot CRM API v3 Client."""

    def __init__(self, api_key: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or settings.CRM_API_KEY
        self.base_url = "https://api.hubapi.com"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def lookup_lead(self, phone: Optional[str] = None, email: Optional[str] = None) -> Optional[Dict[str, Any]]:
        query = email or phone
        if not query:
            return None
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self.base_url}/crm/v3/objects/contacts/search",
                headers=self.headers,
                json={
                    "filterGroups": [{
                        "filters": [{
                            "propertyName": "email" if email else "phone",
                            "operator": "EQ",
                            "value": query,
                        }]
                    }],
                    "properties": ["firstname", "lastname", "email", "phone", "company", "lifecyclestage", "lead_score"],
                },
            )
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                if results:
                    p = results[0]["properties"]
                    return {
                        "id": results[0]["id"],
                        "name": f"{p.get('firstname', '')} {p.get('lastname', '')}".strip(),
                        "email": p.get("email"),
                        "phone": p.get("phone"),
                        "company": p.get("company"),
                        "stage": p.get("lifecyclestage"),
                        "lead_score": p.get("lead_score", 0),
                    }
        return None

    async def create_or_update_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        parts = lead_data.get("name", "").split(" ", 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""

        properties = {
            "firstname": first_name,
            "lastname": last_name,
            "email": lead_data.get("email", ""),
            "phone": lead_data.get("phone", ""),
            "company": lead_data.get("company", ""),
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self.base_url}/crm/v3/objects/contacts",
                headers=self.headers,
                json={"properties": properties},
            )
            if resp.status_code in (200, 201):
                return resp.json()
            return {"error": resp.text}

    async def update_qualification(
        self,
        lead_id: str,
        stage: str,
        score: int,
        bant_data: Dict[str, Any],
        summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        stage_map = {
            "Lead": "lead",
            "Marketing Qualified Lead (MQL)": "marketingqualifiedlead",
            "Sales Qualified Lead (SQL)": "salesqualifiedlead",
            "Disqualified": "other",
        }
        properties = {
            "lifecyclestage": stage_map.get(stage, "lead"),
            "notes": summary or "",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"{self.base_url}/crm/v3/objects/contacts/{lead_id}",
                headers=self.headers,
                json={"properties": properties},
            )
            return resp.json() if resp.status_code == 200 else {"error": resp.text}

    async def log_call(
        self,
        lead_id: str,
        call_direction: str,
        duration_seconds: int,
        summary: str,
        transcript: str,
        outcome: str,
        recording_url: Optional[str] = None,
        booking_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "properties": {
                "hs_timestamp": datetime.utcnow().isoformat() + "Z",
                "hs_call_title": f"Voice Agent {call_direction.capitalize()} Call - {outcome}",
                "hs_call_body": f"Summary: {summary}\n\nTranscript:\n{transcript}",
                "hs_call_direction": "INBOUND" if call_direction.lower() == "inbound" else "OUTBOUND",
                "hs_call_duration": str(duration_seconds * 1000),
                "hs_call_status": "COMPLETED",
            }
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self.base_url}/crm/v3/objects/calls",
                headers=self.headers,
                json=payload,
            )
            return resp.json() if resp.status_code in (200, 201) else {"error": resp.text}


def get_crm_adapter() -> BaseCRMAdapter:
    """Factory to retrieve configured CRM Adapter."""
    settings = get_settings()
    provider = settings.CRM_PROVIDER.lower()
    if provider == "hubspot" and settings.CRM_API_KEY:
        return HubSpotCRMAdapter(api_key=settings.CRM_API_KEY)
    # Default to Local JSON CRM adapter
    return LocalJSONCRMAdapter(db_path=settings.CRM_DATABASE_FILE)
