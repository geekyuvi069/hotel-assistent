# Hotel Guest Assistant

A chat assistant for a hotel website (fictional "Lakeview Grand Hotel"). Guests ask about the property and check room availability. React frontend, FastAPI backend, LLM via OpenRouter.

## Run it

Backend (port 8010; 8000 is often taken):
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # put your OPENROUTER_API_KEY in it (optional, see below)
uvicorn app.main:app --port 8010 --reload
```
Frontend (new terminal):
```bash
cd frontend
npm install
API_URL=http://localhost:8010 npm run dev     # http://localhost:5173
```
Vite proxies `/api` to `API_URL`, so the browser only ever talks to the backend. The API key lives only in `backend/.env` (git-ignored).

**No key?** Leave `OPENROUTER_API_KEY` empty. The app runs in *limited mode*: keyword answers from the same knowledge base, and the availability form still works. Replies are labelled as limited.

Tests: `cd backend && pytest` (25) and `cd frontend && npm test` (7).

## Architecture

```
Browser (React)  --/api/chat-->  FastAPI  --> LLM (OpenRouter, claude-haiku-4.5)
   chat + date form  <-JSON--     |   \--tool call--> check_availability()  (deterministic, mock inventory)
                                  \--> hotel.json (knowledge base: facts + rooms)
                                  \--> keyword fallback (if LLM fails)
```
- **Frontend** ([frontend/src/App.jsx](frontend/src/App.jsx)): chat thread, typing indicator, error alert with "Try again", availability form (native date inputs + guests) that opens automatically when the backend replies `needs_availability_input`, room cards for results. Plain CSS, no UI libs.
- **Backend** ([backend/app/](backend/app)): `main.py` (routes, request-id logging middleware), `llm.py` (one LLM call + tool handling + answer validation), `availability.py` (pure function), `fallback.py` (keyword answers), `kb.py` + `hotel.json` (data), `schemas.py` (validation).
- **Conversation context:** the frontend sends the full message list (max 20) each turn; the backend is stateless.
- **Data flow:** question -> validation -> LLM sees the whole KB in its system prompt and either answers with cited fact ids, or calls `check_availability`. If dates are missing the app asks via the form instead. Availability results come from Python and are returned as-is; the model never states availability or prices.

## API examples

```bash
curl localhost:8010/api/health

curl -X POST localhost:8010/api/chat -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"What time is check-in?"}]}'
# {"reply":"Check-in is from 3:00 PM...","type":"answer","sources":["checkin"],"degraded":false,"request_id":"ab12cd34",...}

# follow-up: send the history
curl -X POST localhost:8010/api/chat -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Is breakfast included?"},{"role":"assistant","content":"Included for Deluxe and Family Suites."},{"role":"user","content":"And for Standard?"}]}'

curl -X POST localhost:8010/api/availability -H 'Content-Type: application/json' \
  -d '{"check_in":"2026-12-24","check_out":"2026-12-27","adults":3}'

# validation error -> 422
curl -X POST localhost:8010/api/availability -H 'Content-Type: application/json' \
  -d '{"check_in":"2026-12-27","check_out":"2026-12-24","adults":2}'
```
`/api/chat` response `type`: `answer` | `fallback` | `needs_availability_input` | `availability` (with an `availability` object). `degraded: true` means the LLM was down and the keyword fallback answered.

## Product and design notes

**Problem.** Guests want quick answers (check-in time, pool, cancellation) and availability without calling or emailing. Staff time goes to repetitive questions; slow answers lose bookings.

**Guest journey.** Open the site -> suggested questions or free text -> answer with follow-ups in the same thread -> "do you have rooms?" -> date form pops up in the chat -> room cards with price and total -> for anything else (booking, unknown) a pointer to the front desk.

**Frontend choices.** Chat is the familiar pattern and supports follow-ups. Dates are collected with a form, not parsed from free text, because dates are error-prone to extract and a form is faster and unambiguous on mobile. Results are cards, not prose, so price/capacity are scannable. Errors show a plain message and a retry, never a blank screen.

**AI vs deterministic.**
| AI (LLM) | Deterministic (code) |
|---|---|
| Understand the question, pick the right facts, phrase a friendly answer, decide when a tool is needed | Availability and pricing, date/guest validation, source-id validation, fallbacks, conversation limits, logging |

**What can go wrong with AI and how it's handled**
- *Invented facts:* system prompt restricts answers to the KB and forbids guessing; every answer must cite `SOURCES` ids; an answer citing a nonexistent id or no source is replaced by the fallback message.
- *Made-up availability/prices:* the model is told to call the tool, and the tool result is rendered by the app; the model's prose is not used for availability. If the model asks for dates in text instead, code detects availability intent and opens the form.
- *Over-promising (e.g. booking):* prompt says the assistant cannot book and must refer to the front desk. This is prompt-level only, so it is not guaranteed (see improvements).
- *Malformed tool arguments:* validated with Pydantic; on failure the guest is asked for the missing details.
- *Model/API down or slow:* 20s timeout, 1 retry, then keyword fallback (`degraded: true`). If even that has no match, the guest gets the front-desk contact.
- *Frontend call fails:* alert with retry; history is preserved. Invalid dates never reach the API.

**Measuring usefulness.** Resolution rate (conversation ends without a front-desk contact), fallback rate and the questions behind it (to find KB gaps), availability-to-booking click-through, thumbs up/down per answer, latency p95, degraded-mode rate.

**Before production**
- Real booking-system integration for availability; the mock has the same signature.
- Auth/rate limiting and per-IP quotas; restrict CORS to the real origin.
- Retrieval instead of stuffing the KB in the prompt once it grows; multilingual support.
- Output check that blocks unsupported claims (e.g. "confirmed", "guaranteed"), not just a prompt rule.
- Streaming responses, conversation persistence, human handoff, PII redaction in logs, an offline eval set run in CI, and a real e2e test (Playwright) against a running stack.

## Test and evaluation scenarios

| # | Scenario | Type | Covered by | Result |
|---|---|---|---|---|
| 1 | "What time is check-in?" answered from KB with source | Normal | `test_grounded_answer`, `test_chat_passes_llm_answer` | Pass |
| 2 | "Which room for three guests?" excludes Standard (cap 2) | Normal | `test_three_guests_excludes_standard` | Pass |
| 3 | Availability asked without dates -> form shown | Missing info | `test_availability_intent_without_tool_call_shows_form`, frontend form test | Pass |
| 4 | Tool call with bad/missing args -> asks for details | Missing info | `test_bad_tool_args_ask_for_input` | Pass |
| 5 | Question with no KB answer -> front-desk fallback | Ambiguous/unsupported | `test_no_sources_is_fallback`, `test_llm_down_unsupported_question_gets_fallback` | Pass |
| 6 | Model cites a fact id that does not exist -> rejected | Hallucination guard | `test_unknown_source_id_is_rejected` | Pass |
| 7 | Sold-out dates excluded; too many guests -> no rooms | Availability | `test_sold_out_dates_excluded`, `test_too_many_guests_returns_no_rooms` | Pass |
| 8 | Reversed dates / 0 guests rejected (API 422, UI blocks) | Bad input | `test_availability_rejects_bad_input`, `test_invalid_input_raises`, frontend "reversed dates" test | Pass |
| 9 | Follow-up question sends whole conversation | Follow-up | frontend follow-up test | Pass |
| 10 | LLM down/no key -> keyword answer, `degraded: true` | Model failure | `test_llm_down_keyword_fallback_answers`, `test_missing_api_key_raises` | Pass |
| 11 | Loading indicator; server error alert + retry; network failure message | Frontend states | 3 frontend tests | Pass |
| 12 | Empty message / assistant-last message rejected | Validation | `test_chat_rejects_empty_and_assistant_last` | Pass |

Observed: 25/25 backend and 7/7 frontend tests pass (mocked LLM). Manual end-to-end in a real browser at 390px width with a live OpenRouter key: questions, follow-up, availability form, room cards all worked, `degraded: false`, no console errors. There is no automated browser e2e test; the manual run is the e2e evidence.

**Known limitations:** availability data is mocked and hard-coded; there is no booking function (the assistant refers to the front desk); the model's booking wording relies on the prompt.

## AI tools used

Claude Code (Claude) for scaffolding, implementation, tests and UI polish; reviewed and verified by running the tests and the app. Runtime model: Claude Haiku 4.5 through OpenRouter.
