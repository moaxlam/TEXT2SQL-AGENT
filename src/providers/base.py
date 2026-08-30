"""Abstract base for LLM providers."""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ChatResponse:
    """Structured response from an LLM provider."""
    content: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    finish_reason: str = ""


class LLMProvider(ABC):
    """All providers implement this interface."""

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> ChatResponse:
        """Send chat messages, return a ChatResponse with content and token usage."""
        ...

    def chat_json(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 4096,
        retries: int = 2,
    ) -> tuple[dict[str, Any], ChatResponse]:
        """Call chat() then parse the response as JSON.
        Returns (parsed_json, chat_response).
        Retries on JSON parse failure.
        """
        last_error = None
        last_response = ChatResponse()
        for attempt in range(retries):
            response = self.chat(messages, temperature=temperature, max_tokens=max_tokens)
            last_response = response
            # Strip markdown code fences if present
            cleaned = re.sub(r"```(?:json)?\s*", "", response.content).strip().rstrip("`")
            try:
                return json.loads(cleaned), response
            except json.JSONDecodeError as e:
                last_error = e
                logger.warning("JSON parse failed (attempt %d/%d): %s", attempt + 1, retries, e)
                if attempt < retries - 1:
                    messages = messages + [
                        {"role": "assistant", "content": response.content},
                        {"role": "user", "content": "Your response was not valid JSON. Return ONLY a valid JSON object, no markdown, no explanation."},
                    ]
        raise ValueError(f"Failed to parse JSON after {retries} attempts: {last_error}")
