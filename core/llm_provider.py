"""
LLM provider abstraction.

Swap providers by changing LLM_PROVIDER in .env — the rest of the app
(main loop, tool dispatch, memory) never needs to know which one is active.
Both providers expose the same `chat(messages, tools)` -> normalized response.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from core.config import Config


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall]
    raw: Any = None


class BaseProvider:
    def chat(self, messages: list[dict], tools: list[dict], system: str) -> LLMResponse:
        raise NotImplementedError

    def tool_result_message(self, tool_call_id: str, name: str, content: str) -> dict:
        raise NotImplementedError


class AnthropicProvider(BaseProvider):
    def __init__(self):
        import anthropic
        self.client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.model = Config.ANTHROPIC_MODEL

    def chat(self, messages, tools, system):
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system,
            messages=messages,
            tools=tools or [],
        )
        text_parts = []
        tool_calls = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, input=block.input))
        return LLMResponse(text="".join(text_parts), tool_calls=tool_calls, raw=resp)

    def assistant_message(self, resp: LLMResponse) -> dict:
        content = []
        if resp.text:
            content.append({"type": "text", "text": resp.text})
        for tc in resp.tool_calls:
            content.append({"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.input})
        return {"role": "assistant", "content": content}

    def tool_result_message(self, tool_call_id, name, content):
        return {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": tool_call_id, "content": content}],
        }


class OpenAIProvider(BaseProvider):
    def __init__(self):
        import openai
        # base_url lets this point at any OpenAI-compatible endpoint,
        # e.g. a local OmniRoute gateway (http://localhost:20128/v1)
        # instead of api.openai.com — see OPENAI_BASE_URL in .env.
        self.client = openai.OpenAI(
            api_key=Config.OPENAI_API_KEY or "not-needed-for-local-gateway",
            base_url=Config.OPENAI_BASE_URL or None,
        )
        self.model = Config.OPENAI_MODEL

    def _to_openai_tools(self, tools):
        # Accepts Anthropic-style tool schema and converts to OpenAI's function format.
        out = []
        for t in tools:
            out.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
                },
            })
        return out

    def chat(self, messages, tools, system):
        full_messages = [{"role": "system", "content": system}] + messages
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                tools=self._to_openai_tools(tools) if tools else None,
            )
        except Exception as e:
            # Many free-tier models behind gateways like OmniRoute don't support
            # function calling (tools) at all and will 400/error on the request.
            # Fall back to a plain text completion so Phin still responds instead
            # of crashing — it just won't be able to call tools on this turn.
            if tools:
                print(f"  [warn] model rejected tool-calling request ({e}); retrying without tools")
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=full_messages,
                )
            else:
                raise
        choice = resp.choices[0].message
        tool_calls = []
        if choice.tool_calls:
            import json
            for tc in choice.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    input=json.loads(tc.function.arguments or "{}"),
                ))
        return LLMResponse(text=choice.content or "", tool_calls=tool_calls, raw=resp)

    def assistant_message(self, resp: LLMResponse) -> dict:
        import json
        msg = {"role": "assistant", "content": resp.text or None}
        if resp.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.input)},
                }
                for tc in resp.tool_calls
            ]
        return msg

    def tool_result_message(self, tool_call_id, name, content):
        return {"role": "tool", "tool_call_id": tool_call_id, "name": name, "content": content}


class FallbackProvider(BaseProvider):
    """
    Multi-tier zero-cost setup with no single point of failure:

      1. Ollama (local, genuinely unlimited — nothing leaves the PC)
      2. Groq (fast official free tier, ~100K tokens/day)
      3. Gemini (larger daily quota, official Google endpoint)

    Ollama goes first when available because it has no rate limit at all —
    Groq/Gemini's daily quotas are only spent as a backup, not the default
    path. Groq still goes before Gemini when Ollama isn't running, since its
    custom inference hardware gives much lower time-to-first-token — this
    matters most for a voice assistant, where the LLM call sits directly in
    the "you finish speaking" -> "Phin starts talking" gap.
    """

    def __init__(self):
        import openai
        self.tiers = []  # list of (label, client, model, supports_tools)

        if Config.OLLAMA_ENABLED:
            try:
                ollama_client = openai.OpenAI(base_url=Config.OLLAMA_BASE_URL, api_key="ollama")
                self.tiers.append(("Ollama", ollama_client, Config.OLLAMA_MODEL, True))
            except Exception:
                pass
        if Config.GROQ_API_KEY:
            self.tiers.append((
                "Groq", openai.OpenAI(api_key=Config.GROQ_API_KEY, base_url=Config.GROQ_BASE_URL),
                Config.GROQ_MODEL, True,
            ))
        if Config.GEMINI_API_KEY:
            # Gemini's OpenAI-compat shim currently 400s on tool_calls responses
            # (missing "thought_signature", a Gemini-specific field the shim
            # doesn't populate). Rather than burn a full round-trip discovering
            # that on every single turn, this tier is marked tools-incapable
            # up front and just goes straight to a plain text call.
            self.tiers.append((
                "Gemini", openai.OpenAI(api_key=Config.GEMINI_API_KEY, base_url=Config.GEMINI_BASE_URL),
                Config.GEMINI_MODEL, False,
            ))

        self._delegate = OpenAIProvider.__new__(OpenAIProvider)  # reuse formatting helpers

    def _to_openai_tools(self, tools):
        return self._delegate._to_openai_tools(tools)

    def _recover_malformed_tool_call(self, error_message: str):
        """
        Groq's llama-3.3-70b-versatile sometimes leaks its internal function-
        call format as plain text instead of a structured tool_calls response,
        e.g.: <function=open_url{"url": "https://x.com"}</function>
        The request then 400s and, left alone, we'd retry without tools and
        the model would just make up an answer instead of actually acting.
        Parse that leaked text back into a real ToolCall so the tool still
        runs and the reply is grounded in what it actually returned.
        """
        import re, json
        m = re.search(r'<function=(\w+)\s*(\{.*?\})\s*(?:</function>)?>?', error_message, re.DOTALL)
        if not m:
            return None
        name, raw_args = m.group(1), m.group(2)
        try:
            args = json.loads(raw_args)
        except Exception:
            return None
        print(f"  [debug] leaked tool-call text: {name}({args})")
        return ToolCall(id=f"recovered_{name}", name=name, input=args)

    def chat(self, messages, tools, system):
        full_messages = [{"role": "system", "content": system}] + messages
        oa_tools = self._to_openai_tools(tools) if tools else None

        def _call(client, model, supports_tools):
            use_tools = oa_tools if supports_tools else None
            try:
                return client.chat.completions.create(
                    model=model, messages=full_messages, tools=use_tools,
                    tool_choice="auto" if use_tools else None,
                    parallel_tool_calls=False if use_tools else None,
                )
            except Exception as e:
                if use_tools:
                    recovered = self._recover_malformed_tool_call(str(e))
                    if recovered:
                        print(f"  [warn] {model} leaked malformed tool-call syntax; recovered {recovered.name} instead of guessing")
                        return LLMResponse(text="", tool_calls=[recovered])
                    print(f"  [warn] {model} rejected tool-calling ({e}); retrying without tools")
                    return client.chat.completions.create(model=model, messages=full_messages)
                raise

        resp = None
        last_error = None
        for label, client, model, supports_tools in self.tiers:
            try:
                resp = _call(client, model, supports_tools)
                break
            except Exception as e:
                last_error = e
                print(f"  [warn] {label} failed ({e}); trying next provider")

        if resp is None:
            names = ", ".join(t[0] for t in self.tiers) or "none configured"
            print(f"  [warn] all providers unavailable this turn ({names}): {last_error}")
            return LLMResponse(
                text=(
                    f"I can't reach any of my configured language models right now "
                    f"({names}). Check the terminal for the exact error — if Ollama "
                    f"is one of them, make sure it's running (`ollama serve`)."
                ),
                tool_calls=[],
            )

        if isinstance(resp, LLMResponse):
            return resp

        choice = resp.choices[0].message
        tool_calls = []
        if choice.tool_calls:
            import json
            for tc in choice.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.id, name=tc.function.name,
                    input=json.loads(tc.function.arguments or "{}"),
                ))
        return LLMResponse(text=choice.content or "", tool_calls=tool_calls, raw=resp)

    def assistant_message(self, resp: LLMResponse) -> dict:
        return self._delegate.assistant_message(resp)

    def tool_result_message(self, tool_call_id, name, content):
        return self._delegate.tool_result_message(tool_call_id, name, content)


def get_provider() -> BaseProvider:
    if Config.LLM_PROVIDER == "fallback":
        return FallbackProvider()
    if Config.LLM_PROVIDER == "openai":
        return OpenAIProvider()
    return AnthropicProvider()
