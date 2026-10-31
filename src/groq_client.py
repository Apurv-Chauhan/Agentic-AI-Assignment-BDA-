import time
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from groq import Groq
from src.config import ensure_api_key, DEFAULT_MODEL, FALLBACK_MODEL

class LLMResponse(BaseModel):
    content: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_seconds: float = 0.0
    model: str = DEFAULT_MODEL

class GroqClientWrapper:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or ensure_api_key()
        self.client = Groq(api_key=self.api_key)
        self.model = model or DEFAULT_MODEL
        self._ensure_valid_model()

    def _ensure_valid_model(self):
        """Auto-detect available models for this API key to prevent 404s."""
        try:
            available = [m.id for m in self.client.models.list().data]
            if self.model not in available:
                for candidate in ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b", "llama-3.3-70b-versatile"]:
                    if candidate in available:
                        self.model = candidate
                        break
        except Exception:
            pass

    def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """
        Execute chat completion with Groq, capturing tool calls, latency, and token usage.
        """
        start_time = time.perf_counter()

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        try:
            response = self.client.chat.completions.create(**kwargs)
        except Exception as e:
            # If primary model encounters rate limit or error, attempt fallback model
            if self.model != FALLBACK_MODEL:
                kwargs["model"] = FALLBACK_MODEL
                response = self.client.chat.completions.create(**kwargs)
            else:
                raise e

        latency = time.perf_counter() - start_time
        choice = response.choices[0]
        message = choice.message

        tool_calls_data = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls_data.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                })

        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else 0

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls_data,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_seconds=round(latency, 3),
            model=kwargs["model"],
        )
