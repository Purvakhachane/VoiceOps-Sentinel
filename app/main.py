from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.models import CallAnalysisResponse, TranscriptAnalysisRequest
from app.pipeline import CallIntelligencePipeline
from app.services.transcription import TranscriptionConfigurationError


ROOT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT_DIR / "frontend"
ALLOWED_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".webm", ".mp4", ".mpeg", ".mpga"}

app = FastAPI(
    title="VoiceOps Sentinel",
    description="Real-time call intelligence for customer support operations.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "VoiceOps Sentinel"}


@app.post("/api/calls", response_model=CallAnalysisResponse)
async def analyze_call(file: UploadFile = File(...)) -> CallAnalysisResponse:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        supported = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Use {supported}.")

    started = time.perf_counter()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        audio_path = Path(tmp.name)

    try:
        pipeline = CallIntelligencePipeline()
        result = pipeline.process(audio_path=audio_path, source_filename=file.filename or "call")
        result.metrics.processing_seconds = round(time.perf_counter() - started, 2)
        return result
    except TranscriptionConfigurationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        audio_path.unlink(missing_ok=True)


@app.post("/api/transcripts", response_model=CallAnalysisResponse)
async def analyze_transcript(payload: TranscriptAnalysisRequest) -> CallAnalysisResponse:
    started = time.perf_counter()
    pipeline = CallIntelligencePipeline()
    result = pipeline.process_text(payload.transcript, payload.source_name)
    result.metrics.processing_seconds = round(time.perf_counter() - started, 2)
    return result
