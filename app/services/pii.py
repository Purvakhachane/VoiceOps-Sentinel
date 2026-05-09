from __future__ import annotations

import os
import re
from collections import Counter

from app.models import TranscriptTurn


PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "phone": re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "account_or_order": re.compile(r"\b(?:order|account|ticket)\s+#?\d{4,}\b", re.IGNORECASE),
}


class PiiRedactor:
    def __init__(self) -> None:
        self._nlp = None
        if os.getenv("VOICEOPS_USE_SPACY", "false").lower() == "true":
            try:
                import spacy

                self._nlp = spacy.load("en_core_web_sm")
            except Exception:
                self._nlp = None

    def redact_turns(self, turns: list[TranscriptTurn]) -> tuple[list[TranscriptTurn], dict[str, int]]:
        counts: Counter[str] = Counter()
        redacted: list[TranscriptTurn] = []
        for turn in turns:
            redacted_text = turn.text
            for label, pattern in PII_PATTERNS.items():
                redacted_text, count = pattern.subn(f"[REDACTED_{label.upper()}]", redacted_text)
                counts[label] += count

            redacted_text, name_count = self._redact_names(redacted_text)
            counts["name"] += name_count
            redacted.append(turn.model_copy(update={"text": redacted_text, "redacted_text": redacted_text}))

        return redacted, dict(counts)

    def _redact_names(self, text: str) -> tuple[str, int]:
        if self._nlp is not None:
            doc = self._nlp(text)
            names = [entity.text for entity in doc.ents if entity.label_ == "PERSON"]
        else:
            names = re.findall(
                r"\b(?:my name is|this is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
                text,
                flags=re.IGNORECASE,
            )

        redacted = text
        count = 0
        for name in sorted(set(names), key=len, reverse=True):
            redacted, replacements = re.subn(re.escape(name), "[REDACTED_NAME]", redacted)
            count += replacements
        return redacted, count
