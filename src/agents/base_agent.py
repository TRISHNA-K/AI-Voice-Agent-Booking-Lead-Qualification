"""Base conversational Voice AI Agent implementation."""

import json
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
import httpx

from config.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger("base_agent")


class BaseVoiceAgent(ABC):
    """Abstract Base Class for Voice AI Agents."""

    def __init__(self, name: str, system_prompt: str):
        self.name = name
        self.system_prompt = system_prompt
        self.settings = get_settings()
        self.conversation_history: List[Dict[str, str]] = []
        self.tools: Dict[str, Callable] = {}
        self.tool_definitions: List[Dict[str, Any]] = []

    def register_tool(self, name: str, func: Callable, definition: Dict[str, Any]):
        """Register an executable tool with its JSON schema."""
        self.tools[name] = func
        self.tool_definitions.append(definition)

    def reset_conversation(self, context: Optional[Dict[str, Any]] = None):
        """Clear conversation history and set initial system prompt with injected context."""
        prompt = self.system_prompt
        if context:
            for k, v in context.items():
                prompt = prompt.replace(f"{{{k}}}", str(v))
        self.conversation_history = [{"role": "system", "content": prompt}]

    @abstractmethod
    async def process_turn(self, user_utterance: str) -> Dict[str, Any]:
        """
        Process a user's spoken turn and produce a conversational response.
        Returns a dict with 'speech', 'tool_calls', and 'action'.
        """
        pass
