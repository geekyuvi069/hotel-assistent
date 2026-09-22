import json
from types import SimpleNamespace as NS

import pytest

from app import llm
from app.schemas import Message

pytestmark = pytest.mark.asyncio
MSGS = [Message(role="user", content="hi")]


def fake(content=None, tool_args=None):
    """Fake OpenAI-style client returning one assistant message (text and/or a tool call)."""
    calls = [NS(function=NS(arguments=tool_args if isinstance(tool_args, str) else json.dumps(tool_args)))] \
        if tool_args is not None else None
    async def create(**kw):
        return NS(choices=[NS(message=NS(content=content, tool_calls=calls))])
    client = NS(chat=NS(completions=NS(create=create)))
    return lambda: client


async def test_grounded_answer(monkeypatch):
    monkeypatch.setattr(llm, "get_client", fake("Pool is open 7-9.\nSOURCES: pool"))
    out = await llm.ask(MSGS)
    assert out == {"type": "answer", "reply": "Pool is open 7-9.", "sources": ["pool"]}


async def test_unknown_source_id_is_rejected(monkeypatch):
    monkeypatch.setattr(llm, "get_client", fake("We have a helipad.\nSOURCES: helipad"))
    assert (await llm.ask(MSGS))["type"] == "fallback"


async def test_no_sources_is_fallback(monkeypatch):
    monkeypatch.setattr(llm, "get_client", fake("I don't know.\nSOURCES: none"))
    assert (await llm.ask(MSGS))["type"] == "fallback"


async def test_tool_call_runs_deterministic_availability(monkeypatch):
    monkeypatch.setattr(llm, "get_client", fake(tool_args={"check_in": "2026-10-01", "check_out": "2026-10-03", "adults": 3}))
    out = await llm.ask(MSGS)
    assert out["type"] == "availability"
    assert [r["id"] for r in out["availability"]["rooms"]] == ["deluxe", "family"]


@pytest.mark.parametrize("args", [
    {"adults": 2},                                                        # missing dates
    {"check_in": "2026-10-03", "check_out": "2026-10-01", "adults": 2},   # reversed dates
    "{not json",                                                          # malformed arguments
])
async def test_bad_tool_args_ask_for_input(monkeypatch, args):
    monkeypatch.setattr(llm, "get_client", fake(tool_args=args))
    assert (await llm.ask(MSGS))["type"] == "needs_availability_input"


async def test_availability_intent_without_tool_call_shows_form(monkeypatch):
    monkeypatch.setattr(llm, "get_client", fake("What dates?\nSOURCES: none"))
    out = await llm.ask([Message(role="user", content="Do you have rooms available?")])
    assert out["type"] == "needs_availability_input"


async def test_missing_api_key_raises(monkeypatch):
    monkeypatch.setattr(llm.settings, "openrouter_api_key", "")
    with pytest.raises(llm.LLMUnavailable):
        await llm.ask(MSGS)
