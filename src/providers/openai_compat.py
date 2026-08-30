"""Generic OpenAI-compatible provider."""

from __future__ import annotations

from openai import OpenAI

from .base import LLMProvider, ChatResponse


class OpenAICompatProvider(LLMProvider):
    def __init__(self, api_key, base_url, model):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def chat(self, messages, temperature=0.0, max_tokens=4096):
        response = self.client.chat.completions.create(
            model=self.model, messages=messages,
            temperature=temperature, max_tokens=max_tokens,
        )
        choice = response.choices[0]
        usage = response.usage
        return ChatResponse(
            content=choice.message.content or "",
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            total_tokens=getattr(usage, "total_tokens", 0) or 0,
            model=response.model or self.model,
            finish_reason=choice.finish_reason or "",
        )
