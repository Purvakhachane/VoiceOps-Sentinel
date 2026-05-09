from __future__ import annotations

import os
import platform
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]


@dataclass
class RawTurn:
    start: float
    end: float
    text: str
    speaker: str | None = None


@dataclass
class TranscriptionResult:
    turns: list[RawTurn]
    duration_seconds: float


class BaseTranscriber:
    mode = "demo"

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        raise NotImplementedError


class TranscriptionConfigurationError(RuntimeError):
    """Raised when no real transcription provider is available."""


class DemoTranscriber(BaseTranscriber):
    mode = "demo"

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        size_factor = max(1, min(4, audio_path.stat().st_size // 500_000 + 1))
        turns = [
            RawTurn(0.0, 4.4, "Thanks for calling Acme Support, this is Priya. How can I help today?"),
            RawTurn(4.5, 10.3, "My name is Daniel Foster and I am angry because I was charged twice for order 54821."),
            RawTurn(10.4, 16.0, "I am sorry about that. Can you confirm the phone number and email on the account?"),
            RawTurn(16.1, 23.0, "It is 415-555-0198 and daniel.foster@example.com. Please do not make me repeat this again."),
            RawTurn(23.2, 31.0, "I found the duplicate payment. I can send a refund form and escalate the billing ticket today."),
            RawTurn(31.2, 38.0, "Good, thank you. Please call me back tomorrow at 3 PM once the refund has started."),
            RawTurn(38.1, 45.0, "Absolutely. I will send the refund form, create the billing escalation, and schedule the callback."),
        ]
        duration = turns[-1].end + (size_factor - 1) * 3
        return TranscriptionResult(turns=turns, duration_seconds=duration)


class WindowsSpeechTranscriber(BaseTranscriber):
    mode = "windows-speech"

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        if audio_path.suffix.lower() != ".wav":
            raise TranscriptionConfigurationError(
                "Real transcription is configured through Windows Speech for WAV files only. "
                "Use a WAV file or configure OPENAI_API_KEY with VOICEOPS_TRANSCRIBER=openai."
            )

        command = (
            "Add-Type -AssemblyName System.Speech; "
            "$rec = New-Object System.Speech.Recognition.SpeechRecognitionEngine; "
            "$rec.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar)); "
            f"$rec.SetInputToWaveFile('{self._escape_path(audio_path)}'); "
            "$result = $rec.Recognize(); "
            "if ($result) { $result.Text }; "
            "$rec.Dispose();"
        )
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        text = completed.stdout.strip()
        if not text:
            detail = completed.stderr.strip() or "The recognizer could not extract speech from this audio."
            raise TranscriptionConfigurationError(detail)

        duration = self._wav_duration(audio_path)
        return TranscriptionResult(
            turns=[RawTurn(start=0.0, end=duration, text=text, speaker="Speaker A")],
            duration_seconds=duration,
        )

    def _wav_duration(self, audio_path: Path) -> float:
        with wave.open(str(audio_path), "rb") as audio:
            frames = audio.getnframes()
            rate = audio.getframerate()
            return round(frames / float(rate), 2) if rate else 0.0

    def _escape_path(self, audio_path: Path) -> str:
        return str(audio_path).replace("'", "''")


class OpenAIWhisperTranscriber(BaseTranscriber):
    mode = "openai-whisper"

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        from openai import OpenAI

        client = OpenAI()
        with audio_path.open("rb") as audio:
            response = client.audio.transcriptions.create(
                model=os.getenv("VOICEOPS_OPENAI_TRANSCRIPTION_MODEL", "whisper-1"),
                file=audio,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )

        turns: list[RawTurn] = []
        segments = getattr(response, "segments", None) or []
        for segment in segments:
            turns.append(
                RawTurn(
                    start=float(segment.get("start", 0) if isinstance(segment, dict) else segment.start),
                    end=float(segment.get("end", 0) if isinstance(segment, dict) else segment.end),
                    text=str(segment.get("text", "") if isinstance(segment, dict) else segment.text).strip(),
                )
            )

        text = getattr(response, "text", "")
        if not turns and text:
            turns.append(RawTurn(start=0.0, end=0.0, text=text.strip()))

        duration = max((turn.end for turn in turns), default=0.0)
        return TranscriptionResult(turns=turns, duration_seconds=duration)


def get_transcriber() -> BaseTranscriber:
    _load_dotenv()
    requested = os.getenv("VOICEOPS_TRANSCRIBER", "auto").lower()
    if os.getenv("OPENAI_API_KEY") and requested in {"auto", "openai"}:
        return OpenAIWhisperTranscriber()
    if requested == "demo":
        return DemoTranscriber()
    if platform.system().lower() == "windows":
        return WindowsSpeechTranscriber()
    if requested == "openai":
        raise TranscriptionConfigurationError(
            "OPENAI_API_KEY is missing, so OpenAI Whisper transcription cannot run."
        )
    raise TranscriptionConfigurationError(
        "No real transcription provider is configured. Set OPENAI_API_KEY and VOICEOPS_TRANSCRIBER=openai, "
        "or set VOICEOPS_TRANSCRIBER=demo only when you want sample data."
    )


def _load_dotenv() -> None:
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)
