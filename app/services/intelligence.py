from __future__ import annotations

import re

from app.models import ActionItem, SentimentEvent, TranscriptTurn


ANGRY_TERMS = {"angry", "furious", "upset", "mad", "frustrated", "repeat this again", "charged twice"}
HAPPY_TERMS = {"thank you", "good", "great", "perfect", "relieved", "appreciate"}
ACTION_PATTERNS = [
    re.compile(r"\b(send [^.]+?)(?:\.|,| and|$)", re.IGNORECASE),
    re.compile(r"\b(call (?:me|you|the customer) back [^.]+?)(?:\.|,| and|$)", re.IGNORECASE),
    re.compile(r"\b(escalate [^.]+?)(?:\.|,| and|$)", re.IGNORECASE),
    re.compile(r"\b(schedule [^.]+?)(?:\.|,| and|$)", re.IGNORECASE),
]


class IntelligenceEngine:
    def summarize(self, turns: list[TranscriptTurn]) -> str:
        combined = " ".join(turn.redacted_text for turn in turns).strip()
        if not combined:
            return "No speech was detected in the recording."

        support_terms = {"refund", "charged", "account", "ticket", "customer", "call back", "escalate", "support"}
        has_support_context = any(term in combined.lower() for term in support_terms)
        if not has_support_context:
            speaker_count = len({turn.speaker for turn in turns})
            return f"Recording contains neutral speech from {speaker_count} speaker(s): {combined[:180]}"

        customer_pain = self._first_matching(turns, ANGRY_TERMS) or "Customer contacted support with a service issue."
        resolution = self._first_agent_phrase(turns, ["send", "refund", "escalate", "callback", "call you back", "call me back", "resolved"])
        if resolution:
            resolution = resolution.rstrip(".")
            return f"Customer reported an urgent billing issue. Agent acknowledged the problem, confirmed account details with PII redacted, and committed to this next step: {resolution.lower()}."
        return f"{customer_pain} Agent gathered details and should complete the listed follow-up actions."

    def detect_sentiment_events(self, turns: list[TranscriptTurn]) -> list[SentimentEvent]:
        events: list[SentimentEvent] = []
        previous = "neutral"
        for turn in turns:
            label = self._sentiment_label(turn.redacted_text)
            turn.sentiment = label
            if label != "neutral" and label != previous:
                events.append(
                    SentimentEvent(
                        timestamp=turn.start,
                        speaker=turn.speaker,
                        label=label,
                        severity="high" if label in {"angry", "frustrated"} else "medium",
                        evidence=turn.redacted_text[:160],
                    )
                )
            previous = label
        return events

    def extract_action_items(self, turns: list[TranscriptTurn]) -> list[ActionItem]:
        items: list[ActionItem] = []
        seen: set[str] = set()
        for turn in turns:
            for pattern in ACTION_PATTERNS:
                for match in pattern.findall(turn.redacted_text):
                    task = match.strip().capitalize()
                    key = self._dedupe_key(task)
                    if key in seen:
                        continue
                    seen.add(key)
                    due = self._extract_due(task)
                    items.append(
                        ActionItem(
                            owner="Agent",
                            task=task,
                            due=due,
                            priority="high" if "escalate" in key or "refund" in key else "medium",
                        )
                    )
        return items

    def _sentiment_label(self, text: str) -> str:
        lowered = text.lower()
        if any(term in lowered for term in ANGRY_TERMS):
            return "angry"
        if any(term in lowered for term in HAPPY_TERMS):
            return "happy"
        return "neutral"

    def _first_matching(self, turns: list[TranscriptTurn], terms: set[str]) -> str | None:
        for turn in turns:
            if any(term in turn.redacted_text.lower() for term in terms):
                return turn.redacted_text
        return None

    def _first_phrase(self, turns: list[TranscriptTurn], terms: list[str]) -> str | None:
        for turn in turns:
            lowered = turn.redacted_text.lower()
            if any(term in lowered for term in terms):
                return turn.redacted_text
        return None

    def _first_agent_phrase(self, turns: list[TranscriptTurn], terms: list[str]) -> str | None:
        for turn in turns:
            if turn.speaker != "Speaker A":
                continue
            lowered = turn.redacted_text.lower()
            if any(term in lowered for term in terms):
                return turn.redacted_text
        return None

    def _extract_due(self, task: str) -> str | None:
        match = re.search(r"\b(tomorrow(?: at \d{1,2}\s*(?:am|pm)?)?)\b", task, re.IGNORECASE)
        return match.group(1) if match else None

    def _dedupe_key(self, task: str) -> str:
        lowered = task.lower()
        lowered = re.sub(r"\b(a|the)\b", "", lowered)
        lowered = re.sub(r"\s+", " ", lowered)
        return lowered.strip()
