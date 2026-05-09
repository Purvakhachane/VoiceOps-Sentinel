from __future__ import annotations

from pydantic import BaseModel, Field


class TranscriptTurn(BaseModel):
    start: float = Field(..., description="Turn start time in seconds.")
    end: float = Field(..., description="Turn end time in seconds.")
    speaker: str = Field(..., description="Speaker A for agent or Speaker B for customer.")
    text: str
    redacted_text: str
    sentiment: str = Field(..., description="happy, neutral, angry, frustrated, or relieved.")


class SentimentEvent(BaseModel):
    timestamp: float
    speaker: str
    label: str
    severity: str
    evidence: str


class ActionItem(BaseModel):
    owner: str
    task: str
    due: str | None = None
    priority: str = "medium"


class CallMetrics(BaseModel):
    duration_seconds: float
    processing_seconds: float = 0
    pii_redactions: dict[str, int]
    transcript_turns: int
    model_mode: str


class CallAnalysisResponse(BaseModel):
    call_id: str
    source_filename: str
    summary: str
    transcript: list[TranscriptTurn]
    redacted_transcript: str
    sentiment_events: list[SentimentEvent]
    action_items: list[ActionItem]
    metrics: CallMetrics


class TranscriptAnalysisRequest(BaseModel):
    transcript: str = Field(..., min_length=1)
    source_name: str = "live-browser-transcript"
