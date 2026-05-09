from __future__ import annotations

import os
from pathlib import Path

from app.models import TranscriptTurn
from app.services.transcription import RawTurn


class BaseDiarizer:
    def assign_speakers(self, turns: list[RawTurn]) -> list[TranscriptTurn]:
        raise NotImplementedError


class AlternatingDiarizer(BaseDiarizer):
    def assign_speakers(self, turns: list[RawTurn]) -> list[TranscriptTurn]:
        output: list[TranscriptTurn] = []
        for index, turn in enumerate(turns):
            speaker = turn.speaker or ("Speaker A" if index % 2 == 0 else "Speaker B")
            output.append(
                TranscriptTurn(
                    start=turn.start,
                    end=turn.end,
                    speaker=speaker,
                    text=turn.text,
                    redacted_text=turn.text,
                    sentiment="neutral",
                )
            )
        return output


class PyannoteDiarizer(BaseDiarizer):
    def __init__(self) -> None:
        self.token = os.getenv("HUGGINGFACE_TOKEN")

    def assign_speakers(self, turns: list[RawTurn]) -> list[TranscriptTurn]:
        # Production hook: run pyannote.audio on the same audio file, then map ASR
        # segment midpoints to the closest diarized speaker interval.
        return AlternatingDiarizer().assign_speakers(turns)


def get_diarizer() -> BaseDiarizer:
    if os.getenv("VOICEOPS_DIARIZER", "").lower() == "pyannote":
        return PyannoteDiarizer()
    return AlternatingDiarizer()

