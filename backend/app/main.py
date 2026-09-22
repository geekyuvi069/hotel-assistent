import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import fallback, llm
from .availability import check_availability
from .schemas import AvailabilityRequest, AvailabilityResult, ChatRequest, ChatResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("api")

app = FastAPI(title="Hotel Guest Assistant")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.id = uuid.uuid4().hex[:8]
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("[%s] unhandled error", request.state.id)
        return JSONResponse({"detail": "Internal error", "request_id": request.state.id}, status_code=500)
    log.info("[%s] %s %s -> %s %.0fms", request.state.id, request.method, request.url.path,
             response.status_code, (time.perf_counter() - start) * 1000)
    return response


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/availability", response_model=AvailabilityResult)
def availability(req: AvailabilityRequest):
    return check_availability(req.check_in, req.check_out, req.adults)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request):
    rid = request.state.id
    try:
        out, degraded = await llm.ask(req.messages), False
    except Exception as e:  # LLM down, timeout, no key: keyword fallback keeps the guest unblocked
        log.warning("[%s] LLM failed (%s: %s), using fallback", rid, type(e).__name__, e)
        out, degraded = fallback.answer(req.messages[-1].content), True
    log.info("[%s] chat type=%s sources=%s degraded=%s", rid, out["type"], out["sources"], degraded)
    return ChatResponse(**out, degraded=degraded, request_id=rid)
