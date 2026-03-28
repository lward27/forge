"""LLM proxy service — sends requests to configured providers."""
import json
import logging
from typing import Any

import httpx

from forge_platform.models.llm_provider import LLMProvider

logger = logging.getLogger(__name__)


def chat_completion(
    provider: LLMProvider,
    messages: list[dict],
    tools: list[dict] | None = None,
) -> dict:
    """Send a chat completion request to the LLM provider. Returns the response."""
    api_url = provider.api_url.rstrip("/")
    api_key = provider.api_key_encrypted  # TODO: decrypt in production

    # Detect provider type and adapt request
    if "anthropic" in api_url.lower():
        return _anthropic_request(api_url, api_key, provider.model, messages, tools)
    else:
        return _openai_request(api_url, api_key, provider.model, messages, tools)


def _openai_request(
    api_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    tools: list[dict] | None,
) -> dict:
    """Standard OpenAI-compatible request (works with OpenAI, Groq, Ollama, vLLM)."""
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    url = f"{api_url}/chat/completions"
    logger.info("LLM request to %s model=%s", url, model)

    with httpx.Client(timeout=120.0) as client:
        resp = client.post(url, json=body, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    choice = data["choices"][0]
    message = choice["message"]
    usage = data.get("usage", {})

    return {
        "content": message.get("content"),
        "tool_calls": message.get("tool_calls"),
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
    }


def _anthropic_request(
    api_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    tools: list[dict] | None,
) -> dict:
    """Anthropic Messages API adapter."""
    # Convert OpenAI messages format to Anthropic format
    system_msg = None
    anthropic_messages = []
    for m in messages:
        if m["role"] == "system":
            system_msg = m["content"]
        elif m["role"] == "tool":
            anthropic_messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": m.get("tool_call_id", ""),
                        "content": m["content"],
                    }
                ],
            })
        else:
            anthropic_messages.append({"role": m["role"], "content": m["content"]})

    # Convert OpenAI tools to Anthropic tools
    anthropic_tools = []
    if tools:
        for t in tools:
            f = t["function"]
            anthropic_tools.append({
                "name": f["name"],
                "description": f.get("description", ""),
                "input_schema": f.get("parameters", {"type": "object", "properties": {}}),
            })

    body: dict[str, Any] = {
        "model": model,
        "max_tokens": 4096,
        "messages": anthropic_messages,
    }
    if system_msg:
        body["system"] = system_msg
    if anthropic_tools:
        body["tools"] = anthropic_tools

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }

    url = f"{api_url}/messages"
    logger.info("Anthropic request to %s model=%s", url, model)

    with httpx.Client(timeout=120.0) as client:
        resp = client.post(url, json=body, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    # Convert Anthropic response to OpenAI format
    content = None
    tool_calls = None

    for block in data.get("content", []):
        if block["type"] == "text":
            content = block["text"]
        elif block["type"] == "tool_use":
            if tool_calls is None:
                tool_calls = []
            tool_calls.append({
                "id": block["id"],
                "type": "function",
                "function": {
                    "name": block["name"],
                    "arguments": json.dumps(block["input"]),
                },
            })

    usage = data.get("usage", {})

    return {
        "content": content,
        "tool_calls": tool_calls,
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
    }
