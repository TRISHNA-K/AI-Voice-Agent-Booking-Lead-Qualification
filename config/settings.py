"""Application Configuration and Environment Settings."""

import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Voice AI Agent System Settings."""

    # Server Configuration
    APP_NAME: str = "Dograh Voice AI Agent Service"
    APP_ENV: str = "development"
    DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    WEBHOOK_BASE_URL: str = "http://localhost:8000"

    # Dograh AI Configuration
    DOGRAH_API_URL: str = "http://localhost:8000"
    DOGRAH_API_KEY: str = "dograh_live_default_key"
    DOGRAH_INBOUND_WORKFLOW_ID: Optional[str] = None
    DOGRAH_OUTBOUND_WORKFLOW_ID: Optional[str] = None
    DOGRAH_TELEPHONY_PROVIDER: str = "twilio"  # twilio, vonage, telnyx, plivo

    # Cal.com Configuration
    CALCOM_API_KEY: str = "cal_live_mock_api_key_12345"
    CALCOM_API_URL: str = "https://api.cal.com/v1"
    CALCOM_EVENT_TYPE_ID: int = 123456
    CALCOM_USERNAME: str = "sales-team"
    CALCOM_TIMEZONE: str = "America/New_York"
    CALCOM_WEBHOOK_SECRET: Optional[str] = "cal_webhook_secret_xyz"

    # CRM Configuration (mock, hubspot, salesforce, pipedrive)
    CRM_PROVIDER: str = "mock"
    CRM_API_KEY: Optional[str] = "mock_crm_api_key"
    CRM_BASE_URL: Optional[str] = "https://api.hubspot.com"
    CRM_DATABASE_FILE: str = "data/mock_crm_database.json"

    # LLM Settings (for conversation simulator and intelligence extraction)
    LLM_PROVIDER: str = "openai"  # openai, anthropic, gemini, groq, mock
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.2

    # Telephony & Human Transfer Escalation
    TELEPHONY_ACCOUNT_SID: Optional[str] = None
    TELEPHONY_AUTH_TOKEN: Optional[str] = None
    TELEPHONY_FROM_NUMBER: str = "+15551234567"
    HUMAN_ESCALATION_PHONE_NUMBER: str = "+18005550199"

    # Business Information
    COMPANY_NAME: str = "NovaTech Solutions"
    AGENT_NAME: str = "Alex"
    SUPPORT_EMAIL: str = "support@novatech-solutions.example"

    # Lead Qualification Criteria
    BANT_MIN_QUALIFIED_SCORE: int = 70
    BANT_MIN_WARM_SCORE: int = 40

    @property
    def has_valid_openai_key(self) -> bool:
        """Check if a real, functional OpenAI API key is configured (not a dummy placeholder)."""
        key = (self.OPENAI_API_KEY or "").strip()
        if not key.startswith("sk-"):
            return False
        if any(token in key.lower() for token in ["your_", "placeholder", "sk-your_openai"]):
            return False
        return len(key) >= 25

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
