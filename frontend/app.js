const audioInput = document.querySelector("#audioInput");
const audioPlayer = document.querySelector("#audioPlayer");
const analyzeButton = document.querySelector("#analyzeButton");
const summaryText = document.querySelector("#summaryText");
const actionList = document.querySelector("#actionList");
const sentimentList = document.querySelector("#sentimentList");
const transcript = document.querySelector("#transcript");
const serviceStatus = document.querySelector("#serviceStatus");
const turnMetric = document.querySelector("#turnMetric");
const piiMetric = document.querySelector("#piiMetric");
const latencyMetric = document.querySelector("#latencyMetric");
const copyButton = document.querySelector("#copyButton");
const modeMetric = document.querySelector("#modeMetric");
const recordButton = document.querySelector("#recordButton");
const stopButton = document.querySelector("#stopButton");
const modeNote = document.querySelector("#modeNote");
const liveButton = document.querySelector("#liveButton");
const liveTranscript = document.querySelector("#liveTranscript");
const analyzeTranscriptButton = document.querySelector("#analyzeTranscriptButton");

let latestResult = null;
let selectedBlob = null;
let selectedFilename = "";
let mediaRecorder = null;
let recordedChunks = [];
let recognition = null;
let recognizing = false;
let finalLiveTranscript = "";

async function checkHealth() {
  try {
    const response = await fetch("/api/health");
    const data = await response.json();
    serviceStatus.textContent = data.status === "ok" ? "Service online" : "Service unavailable";
  } catch {
    serviceStatus.textContent = "Service offline";
  }
}

audioInput.addEventListener("change", () => {
  const file = audioInput.files[0];
  if (!file) return;
  selectedBlob = file;
  selectedFilename = file.name;
  audioPlayer.src = URL.createObjectURL(file);
  analyzeButton.textContent = "Analyze Call";
});

analyzeButton.addEventListener("click", async () => {
  if (!selectedBlob) {
    summaryText.textContent = "Choose or record audio first.";
    return;
  }

  const formData = new FormData();
  formData.append("file", selectedBlob, selectedFilename || "recorded-call.webm");
  analyzeButton.disabled = true;
  analyzeButton.textContent = "Analyzing";

  try {
    const response = await fetch("/api/calls", {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Analysis failed.");
    }
    latestResult = await response.json();
    renderResult(latestResult);
  } catch (error) {
    summaryText.textContent = error.message;
  } finally {
    analyzeButton.disabled = false;
    analyzeButton.textContent = "Analyze Call";
  }
});

recordButton.addEventListener("click", async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recordedChunks = [];
    const mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";
    mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    mediaRecorder.addEventListener("dataavailable", (event) => {
      if (event.data.size > 0) recordedChunks.push(event.data);
    });
    mediaRecorder.addEventListener("stop", () => {
      selectedBlob = new Blob(recordedChunks, { type: mediaRecorder.mimeType || "audio/webm" });
      selectedFilename = "recorded-call.webm";
      audioPlayer.src = URL.createObjectURL(selectedBlob);
      stream.getTracks().forEach((track) => track.stop());
      modeNote.textContent = "Recording captured. Analyze Call will send the captured audio to the configured transcription provider.";
    });
    mediaRecorder.start(1000);
    recordButton.disabled = true;
    stopButton.disabled = false;
    summaryText.textContent = "Recording live audio...";
  } catch (error) {
    summaryText.textContent = `Microphone capture failed: ${error.message}`;
  }
});

stopButton.addEventListener("click", () => {
  if (!mediaRecorder || mediaRecorder.state === "inactive") return;
  mediaRecorder.stop();
  recordButton.disabled = false;
  stopButton.disabled = true;
});

liveButton.addEventListener("click", () => {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    summaryText.textContent = "Live speech recognition is not available in this browser. Paste a transcript into the Live Transcript box and analyze it.";
    return;
  }

  if (recognizing && recognition) {
    recognition.stop();
    return;
  }

  recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = "en-US";
  finalLiveTranscript = liveTranscript.value.trim();
  recognition.onstart = () => {
    recognizing = true;
    liveButton.textContent = "Stop";
    summaryText.textContent = "Listening and transcribing live speech...";
  };
  recognition.onend = () => {
    recognizing = false;
    liveButton.textContent = "Start";
    summaryText.textContent = liveTranscript.value.trim()
      ? "Live transcript captured. Press Analyze Transcript."
      : "No speech was captured.";
  };
  recognition.onerror = (event) => {
    summaryText.textContent = `Live transcription failed: ${event.error}`;
  };
  recognition.onresult = (event) => {
    let interim = "";
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const text = event.results[index][0].transcript.trim();
      if (event.results[index].isFinal) {
        finalLiveTranscript = `${finalLiveTranscript}\n${text}`.trim();
      } else {
        interim = text;
      }
    }
    liveTranscript.value = [finalLiveTranscript, interim].filter(Boolean).join("\n");
  };
  recognition.start();
});

analyzeTranscriptButton.addEventListener("click", async () => {
  const text = liveTranscript.value.trim();
  if (!text) {
    summaryText.textContent = "Capture or paste a transcript first.";
    return;
  }

  analyzeTranscriptButton.disabled = true;
  analyzeTranscriptButton.textContent = "Analyzing";
  try {
    const response = await fetch("/api/transcripts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        transcript: text,
        source_name: "live-browser-transcript",
      }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Transcript analysis failed.");
    }
    latestResult = await response.json();
    renderResult(latestResult);
  } catch (error) {
    summaryText.textContent = error.message;
  } finally {
    analyzeTranscriptButton.disabled = false;
    analyzeTranscriptButton.textContent = "Analyze Transcript";
  }
});

copyButton.addEventListener("click", async () => {
  if (!latestResult) return;
  await navigator.clipboard.writeText(latestResult.redacted_transcript);
  copyButton.textContent = "Copied";
  setTimeout(() => {
    copyButton.textContent = "Copy";
  }, 1200);
});

audioPlayer.addEventListener("timeupdate", () => {
  const current = audioPlayer.currentTime;
  document.querySelectorAll(".turn").forEach((node) => {
    const start = Number(node.dataset.start);
    const end = Number(node.dataset.end);
    node.classList.toggle("active", current >= start && current <= end);
  });
});

function renderResult(result) {
  summaryText.textContent = result.summary;
  turnMetric.textContent = result.metrics.transcript_turns;
  piiMetric.textContent = Object.values(result.metrics.pii_redactions).reduce((sum, value) => sum + value, 0);
  latencyMetric.textContent = `${result.metrics.processing_seconds}s`;
  modeMetric.textContent = result.metrics.model_mode;

  actionList.innerHTML = "";
  result.action_items.forEach((item) => {
    const li = document.createElement("li");
    li.innerHTML = `<strong>${item.owner}</strong><br>${escapeHtml(item.task)}${item.due ? `<br><span>Due: ${escapeHtml(item.due)}</span>` : ""}`;
    actionList.appendChild(li);
  });
  if (!result.action_items.length) {
    actionList.innerHTML = "<li>No concrete follow-up tasks detected.</li>";
  }

  sentimentList.innerHTML = "";
  result.sentiment_events.forEach((event) => {
    const li = document.createElement("li");
    li.className = event.label;
    li.innerHTML = `<strong>${formatTime(event.timestamp)} ${event.speaker}: ${event.label}</strong><br>${escapeHtml(event.evidence)}`;
    sentimentList.appendChild(li);
  });
  if (!result.sentiment_events.length) {
    sentimentList.innerHTML = "<li>No major sentiment shift detected.</li>";
  }

  transcript.innerHTML = "";
  result.transcript.forEach((turn) => {
    const row = document.createElement("div");
    row.className = "turn";
    row.dataset.start = turn.start;
    row.dataset.end = turn.end;
    const speakerClass = turn.speaker === "Speaker B" ? "customer" : "";
    row.innerHTML = `
      <span class="time">${formatTime(turn.start)}</span>
      <span class="speaker ${speakerClass}">${turn.speaker}</span>
      <span>${highlightRedactions(escapeHtml(turn.redacted_text))}</span>
    `;
    transcript.appendChild(row);
  });
}

function formatTime(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60).toString().padStart(2, "0");
  return `${mins}:${secs}`;
}

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#039;",
  })[char]);
}

function highlightRedactions(value) {
  return value.replace(/\[REDACTED_[A-Z_]+\]/g, (match) => `<span class="redacted">${match}</span>`);
}

checkHealth();
