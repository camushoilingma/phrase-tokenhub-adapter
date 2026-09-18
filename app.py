import os
import uuid
import threading
from typing import Optional

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from tokenhub_client import translate_sync
from language_map import SUPPORTED_CODES

load_dotenv()

PHRASE_API_TOKEN = os.getenv("PHRASE_API_TOKEN", "demo-token")

app = FastAPI(title="Phrase BYO → TokenHub HY-MT2 Adapter")

# ── Pydantic models matching Phrase BYO schema v1.0.6 ────────────────

class GlossaryEntry(BaseModel):
    term: str
    translation: str

class Segment(BaseModel):
    idx: Optional[str] = None
    text: str
    metadata: Optional[dict] = None

class TranslateRequest(BaseModel):
    sourceLanguage: str
    targetLanguage: str
    segments: list[Segment]
    glossary: Optional[list[GlossaryEntry]] = None
    metadata: Optional[dict] = None

class TranslatedSegment(BaseModel):
    idx: Optional[str] = None
    text: str
    translatedText: str
    metadata: Optional[dict] = None

class TranslateResponse(BaseModel):
    sourceLanguage: str
    targetLanguage: str
    segments: list[TranslatedSegment]
    metadata: Optional[dict] = None

class StatusResponse(BaseModel):
    status: str

class LanguagePair(BaseModel):
    sourceLanguage: str
    targetLanguage: str

class LanguagesResponse(BaseModel):
    languagePairs: list[LanguagePair]

class TranslateAsyncResponse(BaseModel):
    id: str

class TranslateAsyncStatusResponse(BaseModel):
    status: str
    detail: Optional[str] = None

# ── In-memory async job store (replace with Redis for production) ─────

_jobs: dict[str, dict] = {}
_lock = threading.Lock()

def _run_async_job(job_id: str, req: TranslateRequest):
    try:
        segments_dicts = [s.model_dump() for s in req.segments]
        glossary_dicts = [g.model_dump() for g in req.glossary] if req.glossary else None
        translated = translate_sync(
            req.sourceLanguage, req.targetLanguage, segments_dicts, glossary_dicts
        )
        with _lock:
            _jobs[job_id] = {"status": "done", "result": translated}
    except Exception as e:
        with _lock:
            _jobs[job_id] = {"status": "failed", "detail": str(e)}

# ── Auth ─────────────────────────────────────────────────────────────

def check_auth(request: Request):
    token = request.headers.get("X-Api-Token", "")
    if token != PHRASE_API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Api-Token")

# ── Endpoints ─────────────────────────────────────────────────────────

@app.post("/status")
def status(request: Request):
    check_auth(request)
    return StatusResponse(status="ok")

@app.post("/languages")
def languages(request: Request):
    check_auth(request)
    pairs = []
    for src in SUPPORTED_CODES:
        for tgt in SUPPORTED_CODES:
            if src != tgt:
                pairs.append(LanguagePair(sourceLanguage=src, targetLanguage=tgt))
    return LanguagesResponse(languagePairs=pairs)

@app.post("/translate")
def translate(req: TranslateRequest, request: Request):
    check_auth(request)
    segments_dicts = [s.model_dump() for s in req.segments]
    glossary_dicts = [g.model_dump() for g in req.glossary] if req.glossary else None
    translated = translate_sync(req.sourceLanguage, req.targetLanguage, segments_dicts, glossary_dicts)
    return TranslateResponse(
        sourceLanguage=req.sourceLanguage,
        targetLanguage=req.targetLanguage,
        segments=[TranslatedSegment(**s) for s in translated],
        metadata=req.metadata,
    )

@app.post("/translateAsync")
def translate_async(req: TranslateRequest, request: Request):
    check_auth(request)
    job_id = str(uuid.uuid4())
    with _lock:
        _jobs[job_id] = {"status": "running"}
    threading.Thread(target=_run_async_job, args=(job_id, req), daemon=True).start()
    return TranslateAsyncResponse(id=job_id)

@app.get("/translateAsyncStatus/{job_id}")
def translate_async_status(job_id: str, request: Request):
    check_auth(request)
    with _lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"No job found with id '{job_id}'")
    if job["status"] == "done":
        return TranslateAsyncStatusResponse(status="done", detail="completed successfully")
    elif job["status"] == "failed":
        return TranslateAsyncStatusResponse(status="failed", detail=job.get("detail", "unknown error"))
    return TranslateAsyncStatusResponse(status="running")

@app.get("/translateAsyncResult/{job_id}")
def translate_async_result(job_id: str, request: Request):
    check_auth(request)
    with _lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"No job found with id '{job_id}'")
    if job["status"] != "done":
        raise HTTPException(status_code=400, detail="Translation job not complete")
    result = job["result"]
    return TranslateResponse(
        sourceLanguage="",
        targetLanguage="",
        segments=[TranslatedSegment(**s) for s in result],
    )

# ── Error handlers ────────────────────────────────────────────────────

@app.exception_handler(httpx.HTTPStatusError)
def handle_tokenhub_error(request: Request, exc: httpx.HTTPStatusError):
    status_code = exc.response.status_code
    return JSONResponse(
        status_code=502 if status_code >= 500 else status_code,
        content={"error": f"TokenHub error: {exc.response.text[:200]}"},
    )

@app.exception_handler(Exception)
def handle_generic_error(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": str(exc)})