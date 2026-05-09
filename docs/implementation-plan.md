# VoiceOps Sentinel Implementation Plan

## Production Goal

Improve customer-support efficiency and QA by turning raw call audio into a near-real-time operational artifact:

- who said what
- what sensitive data was removed
- where sentiment changed
- what the agent or manager should do next
- what summary should be written back to support systems

## Week 1: Transcription Pipeline

Deliverables:

- Audio upload endpoint supporting mp3, wav, flac, m4a, and ogg
- Whisper API integration behind a transcriber interface
- Normalized timestamped transcript segments
- Demo fallback so the UI works without paid API credentials

Testing focus:

- Word Error Rate against noisy support-call samples
- File compatibility and timeout behavior
- Segment timestamp sanity checks

## Week 2: Intelligence Layer

Deliverables:

- Summary generation
- Sentiment event detection
- Action item extraction
- Chunk-ready processing boundaries for longer calls

Testing focus:

- Latency after audio completion
- Summary usefulness for QA reviewers
- Action-item precision and recall

## Week 3: Diarization And PII

Deliverables:

- Speaker A/Speaker B assignment layer
- Pyannote integration hook
- Regex and spaCy PII redaction for names, emails, phone numbers, cards, and order/account references

Testing focus:

- Diarization error rate
- Redaction recall on seeded sensitive data
- Ensure final stored transcript is PII-safe by default

## Week 4: Final Packaging

Deliverables:

- Dashboard with audio player and timestamped transcript
- Synced transcript highlighting during playback
- Manager summary, action item, and sentiment panels
- Simulated live feed demo path

Testing focus:

- End-to-end demo flow
- Browser responsiveness
- Clear production migration path for streaming ASR and CRM integration

