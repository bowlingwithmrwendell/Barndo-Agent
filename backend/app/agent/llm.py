"""Claude via the Anthropic Messages API (plain HTTPS, no SDK).

The API key is read from ANTHROPIC_API_KEY on the server and never leaves it.
"""

from __future__ import annotations

import httpx

API_VERSION = "2023-06-01"


class LLMError(RuntimeError):
    pass


class AnthropicClient:
    def __init__(
        self, api_key: str, model: str, base_url: str = "https://api.anthropic.com", client: httpx.Client | None = None
    ):
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set")
        self.model = model
        self.url = base_url.rstrip("/") + "/v1/messages"
        self.http = client or httpx.Client(timeout=60)
        self.headers = {"x-api-key": api_key, "anthropic-version": API_VERSION, "content-type": "application/json"}

    def create(self, *, system: list[dict], messages: list[dict], tools: list[dict], max_tokens: int) -> dict:
        body = {"model": self.model, "max_tokens": max_tokens, "system": system, "messages": messages}
        if tools:
            body["tools"] = tools
        try:
            r = self.http.post(self.url, json=body, headers=self.headers)
        except httpx.HTTPError as exc:
            raise LLMError(f"Could not reach the Anthropic API: {exc}") from exc
        if r.status_code != 200:
            # Never echo the request (it contains the key header); only the API's error message.
            try:
                msg = r.json().get("error", {}).get("message", r.text[:300])
            except ValueError:
                msg = r.text[:300]
            raise LLMError(f"Anthropic API error {r.status_code}: {msg}")
        return r.json()
