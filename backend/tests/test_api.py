import pytest
from fastapi.testclient import TestClient

from app import llm
from app.main import app

client = TestClient(app)


def chat(*texts):
    msgs = [{"role": "user" if i % 2 == 0 else "assistant", "content": t} for i, t in enumerate(texts)]
    return client.post("/api/chat", json={"messages": msgs})


@pytest.fixture
def llm_down(monkeypatch):
    async def boom(messages):
        raise RuntimeError("upstream 503")
    monkeypatch.setattr(llm, "ask", boom)


def test_availability_ok():
    r = client.post("/api/availability", json={"check_in": "2026-10-01", "check_out": "2026-10-03", "adults": 3})
    assert r.status_code == 200
    assert [x["id"] for x in r.json()["rooms"]] == ["deluxe", "family"]


@pytest.mark.parametrize("body", [
    {"check_in": "2026-10-03", "check_out": "2026-10-01", "adults": 2},
    {"check_in": "2026-10-01", "check_out": "2026-10-03", "adults": 0},
    {"check_in": "not-a-date", "check_out": "2026-10-03", "adults": 2},
])
def test_availability_rejects_bad_input(body):
    assert client.post("/api/availability", json=body).status_code == 422


def test_chat_rejects_empty_and_assistant_last():
    assert client.post("/api/chat", json={"messages": []}).status_code == 422
    assert client.post("/api/chat", json={"messages": [{"role": "assistant", "content": "hi"}]}).status_code == 422


def test_chat_passes_llm_answer(monkeypatch):
    async def ok(messages):
        return {"type": "answer", "reply": "Check-in is 3 PM.", "sources": ["checkin"]}
    monkeypatch.setattr(llm, "ask", ok)
    body = chat("What time is check-in?").json()
    assert body["type"] == "answer" and body["degraded"] is False and body["request_id"]


def test_llm_down_keyword_fallback_answers(llm_down):
    body = chat("Do you have a swimming pool?").json()
    assert body["degraded"] is True and body["type"] == "answer" and "pool" in body["reply"].lower()


def test_llm_down_availability_still_prompts_form(llm_down):
    assert chat("Any rooms available?").json()["type"] == "needs_availability_input"


def test_llm_down_unsupported_question_gets_fallback(llm_down):
    body = chat("Do you have a helipad?").json()
    assert body["type"] == "fallback" and "front desk" in body["reply"]
