"""LLM-controlled boxer: render the context to text, call the model, parse to a validated action."""
from pathlib import Path

from .llm_client import call_llm
from .schema import parse_action
from .observation import render_observation

_SYSTEM = (Path(__file__).parent / "prompts" / "boxer_system.txt").read_text(encoding="utf-8")


class BoxerAgent:
    def __init__(self, name: str, model: str = "gpt-5-nano",
                 reasoning_effort: str | None = "low", provider: str = "openai"):
        self.name = name
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.provider = provider
        self.call_count = 0
        self.parse_errors = 0

    def decide(self, ctx: dict) -> dict:
        obs = render_observation(ctx)
        raw = call_llm(_SYSTEM, obs, self.model, self.reasoning_effort, self.provider)
        self.call_count += 1
        act = parse_action(raw, ctx)
        if act["reasoning"] in ("parse_error", "fallback: cover up"):
            self.parse_errors += 1
        return act
