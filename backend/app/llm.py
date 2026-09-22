import json
import logging

from openai import AsyncOpenAI
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from .availability import check_availability
from .fallback import AVAILABILITY
from .kb import VALID_IDS, split_sources, system_prompt
from .schemas import AvailabilityRequest, Message

log = logging.getLogger("llm")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    openrouter_api_key: str = ""
    model: str = "anthropic/claude-haiku-4.5"


settings = Settings()

TOOL = {
    "type": "function",
    "function": {
        "name": "check_availability",
        "description": "Check room availability. Call whenever the guest asks about available rooms or booking dates.",
        "parameters": {
            "type": "object",
            "properties": {
                "check_in": {"type": "string", "description": "YYYY-MM-DD"},
                "check_out": {"type": "string", "description": "YYYY-MM-DD"},
                "adults": {"type": "integer"},
            },
        },
    },
}
NEED_INPUT = "Sure, I can check that. Please give me your check-in date, check-out date and number of guests."
NO_ANSWER = "I'm not able to answer that reliably. Please contact our front desk at +91 98765 43210."


class LLMUnavailable(Exception):
    pass


def get_client() -> AsyncOpenAI:
    if not settings.openrouter_api_key:
        raise LLMUnavailable("OPENROUTER_API_KEY not set")
    return AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=settings.openrouter_api_key,
                       timeout=20, max_retries=1)


async def ask(messages: list[Message]) -> dict:
    """One LLM call. The model may answer from the KB or request the availability tool.
    The tool runs in Python and its result is returned as-is: the model never states availability."""
    resp = await get_client().chat.completions.create(
        model=settings.model, max_tokens=500, tools=[TOOL],
        messages=[{"role": "system", "content": system_prompt()}, *[m.model_dump() for m in messages]],
    )
    msg = resp.choices[0].message

    if msg.tool_calls:
        try:
            req = AvailabilityRequest(**json.loads(msg.tool_calls[0].function.arguments or "{}"))
            result = check_availability(req.check_in, req.check_out, req.adults)
        except (ValidationError, TypeError, ValueError):  # JSONDecodeError is a ValueError
            return {"type": "needs_availability_input", "reply": NEED_INPUT, "sources": []}
        n = len(result["rooms"])
        reply = (f"{n} room type(s) available for {result['nights']} night(s)." if n
                 else "Sorry, no rooms are available for those dates and party size.")
        return {"type": "availability", "reply": reply, "availability": result, "sources": []}

    reply, sources = split_sources(msg.content or "")
    # Models often ask for dates in text instead of calling the tool; intent detection stays in code.
    if not sources and any(k in messages[-1].content.lower() for k in AVAILABILITY):
        return {"type": "needs_availability_input", "reply": NEED_INPUT, "sources": []}
    if not reply or not set(sources) <= VALID_IDS:  # cited a fact that doesn't exist -> don't trust it
        log.warning("rejected answer, sources=%s", sources)
        return {"type": "fallback", "reply": NO_ANSWER, "sources": []}
    return {"type": "answer" if sources else "fallback", "reply": reply, "sources": sources}
