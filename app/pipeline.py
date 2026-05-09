from __future__ import annotations

import hashlib
import re
from pathlib import Path

from app.models import CallAnalysisResponse, CallMetrics
from app.models import TranscriptTurn
from app.services.diarization import get_diarizer
from app.services.intelligence import IntelligenceEngine
from app.services.pii import PiiRedactor
from app.services.transcription import get_transcriber


class CallIntelligencePipeline:
    def __init__(self) -> None:
        self.transcriber = get_transcriber()
        self.diarizer = get_diarizer()
        self.redactor = PiiRedactor()
        self.intelligence = IntelligenceEngine()

    def process(self, audio_path: Path, source_filename: str) -> CallAnalysisResponse:
        transcript = self.transcriber.transcribe(audio_path)
        diarized_turns = self.diarizer.assign_speakers(transcript.turns)
        return self._analyze_turns(
            turns=diarized_turns,
            call_id=hashlib.sha1(f"{source_filename}:{audio_path.stat().st_size}".encode()).hexdigest()[:12],
            source_filename=source_filename,
            duration_seconds=transcript.duration_seconds,
            model_mode=self.transcriber.mode,
        )

    def process_text(self, transcript_text: str, source_name: str) -> CallAnalysisResponse:
        turns = self._turns_from_text(transcript_text)
        call_id = hashlib.sha1(f"{source_name}:{transcript_text}".encode()).hexdigest()[:12]
        return self._analyze_turns(
            turns=turns,
            call_id=call_id,
            source_filename=source_name,
            duration_seconds=max((turn.end for turn in turns), default=0.0),
            model_mode="browser-live-speech",
        )

    def _analyze_turns(
        self,
        turns: list[TranscriptTurn],
        call_id: str,
        source_filename: str,
        duration_seconds: float,
        model_mode: str,
    ) -> CallAnalysisResponse:
        diarized_turns = turns
        redacted_turns, redaction_counts = self.redactor.redact_turns(diarized_turns)
        summary = self.intelligence.summarize(redacted_turns)
        sentiment_events = self.intelligence.detect_sentiment_events(redacted_turns)
        action_items = self.intelligence.extract_action_items(redacted_turns)

        return CallAnalysisResponse(
            call_id=call_id,
            source_filename=source_filename,
            summary=summary,
            transcript=redacted_turns,
            redacted_transcript="\n".join(
                f"[{turn.start:05.1f}-{turn.end:05.1f}] {turn.speaker}: {turn.redacted_text}"
                for turn in redacted_turns
            ),
            sentiment_events=sentiment_events,
            action_items=action_items,
            metrics=CallMetrics(
                duration_seconds=duration_seconds,
                pii_redactions=redaction_counts,
                transcript_turns=len(redacted_turns),
                model_mode=model_mode,
            ),
        )

    def _turns_from_text(self, transcript_text: str) -> list[TranscriptTurn]:
        lines = [line.strip() for line in transcript_text.splitlines() if line.strip()]
        if not lines:
            lines = [transcript_text.strip()]

        turns: list[TranscriptTurn] = []
        elapsed = 0.0
        for index, line in enumerate(lines):
            speaker, text = self._parse_speaker_line(line, index)
            chunks = self._split_into_chunks(text)
            for chunk in chunks:
                duration = max(2.5, min(8.0, len(chunk.split()) * 0.55))
                turns.append(
                    TranscriptTurn(
                        start=round(elapsed, 1),
                        end=round(elapsed + duration, 1),
                        speaker=speaker,
                        text=chunk,
                        redacted_text=chunk,
                        sentiment="neutral",
                    )
                )
                elapsed += duration
        return turns

    def _parse_speaker_line(self, line: str, index: int) -> tuple[str, str]:
        match = re.match(r"^(agent|speaker a|customer|speaker b)\s*:\s*(.+)$", line, re.IGNORECASE)
        if not match:
            return ("Speaker A" if index % 2 == 0 else "Speaker B"), line
        label = match.group(1).lower()
        speaker = "Speaker A" if label in {"agent", "speaker a"} else "Speaker B"
        return speaker, match.group(2).strip()

    def _split_into_chunks(self, text: str) -> list[str]:
        chunks = [chunk.strip() for chunk in re.split(r"(?<=[.!?])\s+", text) if chunk.strip()]
        return chunks or [text]
