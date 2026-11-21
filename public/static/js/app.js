import { isAIReady, generateQuestionSet, generateHotTake, coachTranscript } from "./firebase-ai.js";
import {
  getDailyUsage,
  reserveDailyUsage,
  releaseDailyReservation,
  consumeDailyReservation,
  saveSession,
  appendRetry,
  getSession,
  listSessions,
  deleteSession
} from "./local-store.js";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const state = {
  view: "practice",
  goal: "Interview",
  questions: [],
  unlocked: 3,
  completed: new Set(),
  selectedPrompt: null,
  hotTake: null,
  session: null,
  reservationId: null,
  attempt: 1,
  transcript: "",
  finalTranscript: "",
  recognition: null,
  stream: null,
  audioContext: null,
  animationFrame: null,
  timerHandle: null,
  prepHandle: null,
  startedAt: 0,
  endsAt: 0,
  duration: 60,
  lastMilestone: null,
  fillerCounts: {},
  busy: false
};

const fillerTerms = ["um", "uh", "like", "kind of", "basically", "you know"];

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
}

function friendlyMessage(message) {
  const text = String(message ?? "Something went wrong.");
  if (/database connection is closing|InvalidStateError|transaction.*inactive|database.*closed/i.test(text)) {
    return "Local history was interrupted. Your response is still on screen; please try again.";
  }
  if (/QuotaExceededError|storage quota/i.test(text)) {
    return "This browser is low on storage. Remove some site data or download anything you need before continuing.";
  }
  return text;
}

function toast(message, type = "info") {
  const element = $("#toast");
  element.textContent = friendlyMessage(message);
  element.className = `toast show ${type}`;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => element.classList.remove("show"), 4200);
}

function setBusy(button, busy, label = "Working…") {
  if (!button) return;
  if (busy) {
    button.dataset.originalLabel = button.textContent;
    button.disabled = true;
    button.textContent = label;
  } else {
    button.disabled = false;
    if (button.dataset.originalLabel) button.textContent = button.dataset.originalLabel;
  }
}

function setAIStatus(text, type = "ready") {
  const pill = $("#ai-status");
  pill.hidden = false;
  pill.className = `status-pill status-${type}`;
  pill.querySelector("span:last-child").textContent = text;
}

window.addEventListener("speakeasy:ai-status", (event) => {
  setAIStatus(event.detail.text, event.detail.kind === "ready" ? "ready" : event.detail.kind === "cloud" ? "cloud" : event.detail.kind === "error" ? "error" : "pending");
});

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status}).`);
  return payload;
}

async function refreshUsage() {
  try {
    const limit = Number(window.SPEAKEASY_CONFIG?.dailyLimit || 5);
    const usage = await getDailyUsage(limit);
    $("#question-set-help").textContent = `14 questions · ${Math.max(0, usage.limit - usage.used)} of ${usage.limit} free sessions left today on this browser.`;
  } catch (error) {
    console.warn("Local usage could not be loaded.", error);
    $("#question-set-help").textContent = "14 questions · Session allowance is stored in this browser.";
  }
}

async function switchView(view) {
  if (state.busy) return;
  await closeSessionPanel();
  state.view = view;
  $$(".nav-link").forEach((button) => {
    const active = button.dataset.view === view;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });

  const historyActive = view === "history";
  $("#view-practice").hidden = historyActive;
  $("#view-practice").classList.toggle("active", !historyActive);
  $("#view-history").hidden = !historyActive;
  $("#view-history").classList.toggle("active", historyActive);

  if (historyActive) {
    await loadHistory();
  } else if (view === "arena") {
    requestAnimationFrame(() => $("#hot-takes").scrollIntoView({ behavior: "smooth", block: "start" }));
  } else {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
}

function renderQuestions() {
  const list = $("#question-list");
  if (!state.questions.length) {
    list.innerHTML = '<div class="empty-state compact-empty"><p>Generate a question set to begin.</p></div>';
    return;
  }
  list.innerHTML = state.questions.map((question, index) => {
    const unlocked = index < state.unlocked;
    const completed = state.completed.has(index);
    return `<button class="question-item ${unlocked ? "" : "locked"} ${completed ? "completed" : ""}" data-question-index="${index}" ${unlocked ? "" : "disabled"}>
      <span class="question-index">${String(index + 1).padStart(2, "0")}</span>
      <span class="question-text">${escapeHtml(question)}</span>
      <span class="question-state">${completed ? "Completed ✓" : unlocked ? "Start drill →" : "Locked"}</span>
    </button>`;
  }).join("");
}

async function onGenerateQuestions() {
  if (state.busy) return;
  const button = $("#generate-questions");
  state.busy = true;
  setBusy(button, true, "Generating questions…");
  try {
    const result = await generateQuestionSet(state.goal, $("#job-description").value);
    state.questions = result.questions;
    state.unlocked = 3;
    state.completed = new Set();
    renderQuestions();
    toast(`14 questions generated · ${sourceLabel(result.inferenceSource)}`, "success");
  } catch (error) {
    toast(error.message, "error");
  } finally {
    state.busy = false;
    setBusy(button, false);
    refreshUsage();
  }
}

function sourceLabel(source) {
  if (source === "ON_DEVICE") return "On-device · Gemini Nano";
  if (source === "IN_CLOUD") return "Cloud · Gemini";
  return "Inference source not reported";
}

function renderHotTake(result, category, heat) {
  state.hotTake = { ...result, category, heat };
  $("#hot-meta-category").textContent = category;
  $("#hot-meta-heat").textContent = heat.toUpperCase();
  $("#hot-take-statement").textContent = result.statement;
  const constraint = $("#hot-take-constraint");
  constraint.hidden = !result.constraint;
  constraint.textContent = result.constraint ? `Constraint: do not use “${result.constraint}”.` : "";
  $("#hot-prompt-source").textContent = sourceLabel(result.inferenceSource);
  $("#hot-take-result").hidden = false;
}

async function onGenerateHotTake() {
  if (state.busy) return;
  const button = $("#generate-hot-take");
  state.busy = true;
  setBusy(button, true, "Finding your angle…");
  try {
    const category = $("#hot-category").value;
    const heat = $("input[name='heat']:checked").value;
    const result = await generateHotTake(category, heat, $("#custom-topic").value);
    renderHotTake(result, category, heat);
  } catch (error) {
    toast(error.message, "error");
  } finally {
    state.busy = false;
    setBusy(button, false);
  }
}

function openSession(session) {
  state.session = session;
  state.attempt = 1;
  $("#start-recording").textContent = "Start speaking ●";
  state.transcript = "";
  state.finalTranscript = "";
  state.reservationId = null;
  $("#live-transcript").value = "";
  $("#session-prompt").textContent = session.prompt;
  $("#session-mode-label").textContent = session.mode === "hot-take" ? "90-SECOND HOT TAKE" : "60-SECOND DRILL";
  const constraint = $("#session-constraint");
  constraint.hidden = !session.constraint_phrase;
  constraint.textContent = session.constraint_phrase ? `Your constraint: do not use “${session.constraint_phrase}”.` : "";
  state.duration = session.mode === "hot-take" ? 90 : 60;
  $("#timer-value").textContent = formatTime(state.duration);
  $("#timer-caption").textContent = "TIME TO SPEAK";
  $("#filler-total").textContent = "0";
  updateFillerCounts("");
  $("#recording-status").textContent = "Ready when you are. Audio stays in this browser.";
  $("#word-count").textContent = "0 words";
  $("#session-panel").hidden = false;
  $("#scorecard-panel").hidden = true;
  $("#start-recording").hidden = false;
  $("#start-recording").disabled = false;
  $("#stop-recording").disabled = true;
  window.scrollTo({ top: $("#session-panel").offsetTop - 18, behavior: "smooth" });
}

async function closeSessionPanel() {
  if (!$("#session-panel")) return;
  if (state.timerHandle || state.prepHandle || state.recognition || state.stream || state.audioContext) {
    await stopCapture(false);
  }
  await releaseReservation();
  $("#session-panel").hidden = true;
  $("#scorecard-panel").hidden = true;
}

function formatTime(seconds) {
  const remaining = Math.max(0, Math.ceil(seconds));
  return `${String(Math.floor(remaining / 60)).padStart(2, "0")}:${String(remaining % 60).padStart(2, "0")}`;
}

function countFillers(text) {
  const output = {};
  for (const term of fillerTerms) {
    const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\s+/g, "\\s+");
    const matches = text.match(new RegExp(`(?:^|[^\\p{L}\\p{N}_])${escaped}(?=$|[^\\p{L}\\p{N}_])`, "giu"));
    output[term] = matches ? matches.length : 0;
  }
  return output;
}

function updateFillerCounts(text) {
  state.fillerCounts = countFillers(text);
  const total = Object.values(state.fillerCounts).reduce((sum, value) => sum + value, 0);
  $("#filler-total").textContent = total;
  for (const term of fillerTerms) {
    const element = document.querySelector(`[data-filler="${term}"]`);
    if (element) element.textContent = state.fillerCounts[term];
  }
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  $("#word-count").textContent = `${words} ${words === 1 ? "word" : "words"}`;
}

function setTranscript(text) {
  state.transcript = text.slice(0, 12000);
  $("#live-transcript").value = state.transcript;
  updateFillerCounts(state.transcript);
}

async function reserveUsage() {
  const limit = Number(window.SPEAKEASY_CONFIG?.dailyLimit || 5);
  const reservation = await reserveDailyUsage(limit, state.session.mode);
  state.reservationId = reservation.reservationId;
  await refreshUsage();
}

async function releaseReservation() {
  if (!state.reservationId) return;
  try {
    await releaseDailyReservation(state.reservationId);
    await refreshUsage();
  } catch (error) {
    console.warn("Unable to release the unused local session allowance.", error);
  }
  state.reservationId = null;
}

async function prepareMicrophone() {
  if (!navigator.mediaDevices?.getUserMedia) {
    $("#recording-status").textContent = "Microphone capture is unavailable. Type your response below.";
    return null;
  }
  try {
    state.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true }, video: false });
    startWaveform(state.stream);
    return state.stream;
  } catch (error) {
    $("#recording-status").textContent = "Microphone permission was unavailable. You can type your response instead.";
    return null;
  }
}

function startWaveform(stream) {
  try {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return;
    state.audioContext = new AudioContextClass();
    const source = state.audioContext.createMediaStreamSource(stream);
    const analyser = state.audioContext.createAnalyser();
    analyser.fftSize = 64;
    source.connect(analyser);
    const values = new Uint8Array(analyser.frequencyBinCount);
    const bars = $$("#waveform i");
    $("#waveform").classList.add("active");
    const draw = () => {
      analyser.getByteFrequencyData(values);
      bars.forEach((bar, index) => {
        const value = values[index % values.length] / 255;
        bar.style.transform = `scaleY(${0.22 + value * 1.8})`;
      });
      state.animationFrame = requestAnimationFrame(draw);
    };
    draw();
  } catch (error) {
    console.info("Waveform is unavailable; audio capture remains local.", error);
  }
}

async function createLocalRecognizer() {
  const Constructor = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Constructor) {
    $("#recording-status").textContent = "Local speech-to-text is unavailable. Type your response; no remote recognition is used.";
    return null;
  }
  const recognition = new Constructor();
  if (!("processLocally" in recognition)) {
    $("#recording-status").textContent = "This browser cannot guarantee local speech recognition. Type your response instead.";
    return null;
  }
  recognition.lang = "en-US";
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.processLocally = true;
  if (typeof Constructor.available === "function") {
    try {
      let status = await Constructor.available({ langs: ["en-US"], processLocally: true });
      if ((status === "downloadable" || status === "downloading") && typeof Constructor.install === "function") {
        $("#recording-status").textContent = "Preparing the local English speech model…";
        const installed = await Constructor.install({ langs: ["en-US"] });
        if (installed) status = "available";
      }
      if (status !== "available") {
        $("#recording-status").textContent = "Local English speech recognition is not ready. Type your response instead.";
        return null;
      }
    } catch (error) {
      $("#recording-status").textContent = "The local speech model could not be prepared. Type your response instead.";
      return null;
    }
  }
  state.finalTranscript = "";
  recognition.onresult = (event) => {
    let interim = "";
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const item = event.results[index];
      const text = item[0]?.transcript || "";
      if (item.isFinal) state.finalTranscript += `${text.trim()} `;
      else interim += text;
    }
    setTranscript(`${state.finalTranscript}${interim}`.trim());
  };
  recognition.onerror = (event) => {
    const messages = {
      "not-allowed": "Microphone access was blocked. Type your response instead.",
      "service-not-allowed": "Local recognition is unavailable. Remote recognition is disabled.",
      "language-not-supported": "The local English speech model is unavailable.",
      "audio-capture": "The microphone could not be accessed."
    };
    $("#recording-status").textContent = messages[event.error] || `Speech recognition stopped (${event.error}). You can type instead.`;
  };
  recognition.onstart = () => { $("#recording-status").textContent = "Recording · local speech recognition active"; };
  state.recognition = recognition;
  return recognition;
}

async function beginCapture({ hotPrep = false, retry = false } = {}) {
  if (state.busy) return;
  state.busy = true;
  $("#start-recording").disabled = true;
  try {
    // Invoke getUserMedia directly from the user's click before awaiting network work.
    await prepareMicrophone();
    if (!retry) await reserveUsage();
    const recognizer = await createLocalRecognizer();
    if (hotPrep) {
      await runPrepCountdown();
    }
    if (recognizer) {
      try { recognizer.start(); }
      catch (error) { $("#recording-status").textContent = "Local recognition could not start. Type your response instead."; }
    }
    startTimer();
    $("#start-recording").hidden = true;
    $("#stop-recording").disabled = false;
    $("#live-transcript").focus({ preventScroll: true });
  } catch (error) {
    await releaseReservation();
    await stopCapture(false);
    toast(error.message, "error");
    $("#start-recording").disabled = false;
  } finally {
    state.busy = false;
  }
}

function runPrepCountdown() {
  return new Promise((resolve) => {
    const panel = $("#prep-panel");
    panel.hidden = false;
    let remaining = 5;
    $("#prep-countdown").textContent = remaining;
    const run = () => {
      remaining -= 1;
      if (remaining <= 0) {
        clearInterval(state.prepHandle);
        state.prepHandle = null;
        panel.hidden = true;
        resolve();
        return;
      }
      $("#prep-countdown").textContent = remaining;
    };
    state.prepHandle = setInterval(run, 1000);
  });
}

function startTimer() {
  state.startedAt = Date.now();
  state.endsAt = state.startedAt + state.duration * 1000;
  state.lastMilestone = null;
  $("#timer-caption").textContent = "TIME TO SPEAK";
  updateTimer();
  state.timerHandle = setInterval(updateTimer, 200);
}

function updateTimer() {
  const remaining = Math.max(0, (state.endsAt - Date.now()) / 1000);
  $("#timer-value").textContent = formatTime(remaining);
  if (remaining <= 30 && remaining > 10 && state.lastMilestone !== 30) {
    state.lastMilestone = 30;
    $("#recording-status").textContent = "30 seconds left.";
  } else if (remaining <= 10 && remaining > 0 && state.lastMilestone !== 10) {
    state.lastMilestone = 10;
    $("#recording-status").textContent = "10 seconds left. Finish your point.";
  }
  if (remaining <= 0) {
    clearInterval(state.timerHandle);
    state.timerHandle = null;
    $("#timer-caption").textContent = "TIME IS UP";
    stopRecordingAndCoach();
  }
}

async function stopCapture(keepTranscript = true) {
  if (state.timerHandle) clearInterval(state.timerHandle);
  if (state.prepHandle) clearInterval(state.prepHandle);
  state.timerHandle = null;
  state.prepHandle = null;
  if (state.recognition) {
    const recognition = state.recognition;
    await new Promise((resolve) => {
      let finished = false;
      const done = () => {
        if (finished) return;
        finished = true;
        clearTimeout(timeout);
        recognition.removeEventListener("end", done);
        recognition.removeEventListener("error", done);
        resolve();
      };
      const timeout = setTimeout(done, 1200);
      recognition.addEventListener("end", done, { once: true });
      recognition.addEventListener("error", done, { once: true });
      try { recognition.stop(); } catch { done(); }
    });
    state.recognition = null;
  }
  if (state.animationFrame) cancelAnimationFrame(state.animationFrame);
  state.animationFrame = null;
  $("#waveform").classList.remove("active");
  $$("#waveform i").forEach((bar) => { bar.style.transform = "scaleY(.22)"; });
  if (state.stream) {
    state.stream.getTracks().forEach((track) => track.stop());
    state.stream = null;
  }
  if (state.audioContext) {
    await state.audioContext.close().catch(() => {});
    state.audioContext = null;
  }
  if (keepTranscript) {
    state.transcript = $("#live-transcript").value.trim();
    updateFillerCounts(state.transcript);
  }
}

async function stopRecordingAndCoach() {
  $("#stop-recording").disabled = true;
  $("#recording-status").textContent = "Finishing local speech recognition…";
  await stopCapture(true);
  if (state.transcript.trim().length < 5) {
    $("#recording-status").textContent = "Add your response in the transcript box, then select Analyse response.";
    $("#start-recording").hidden = true;
    $("#analyse-response").hidden = false;
    return;
  }
  await analyseResponse();
}

async function analyseResponse() {
  if (state.busy) return;
  const transcript = $("#live-transcript").value.trim();
  if (transcript.length < 5) {
    toast("Add a little more to your transcript before analysis.", "error");
    return;
  }
  const button = $("#analyse-response");
  button.hidden = false;
  state.busy = true;
  setBusy(button, true, "Coaching your response…");
  state.transcript = transcript;
  const duration = Math.max(1, Math.min(state.duration, Math.round((Date.now() - state.startedAt) / 1000)));
  let sessionSaved = false;
  try {
    if (state.attempt === 1 && !state.reservationId) await reserveUsage();
    const fillerCounts = countFillers(transcript);
    const coaching = await coachTranscript({
      transcript,
      prompt: state.session.prompt,
      mode: state.session.mode,
      goal: state.session.goal || "",
      category: state.session.category || "",
      heat: state.session.heat || "",
      durationSeconds: duration,
      fillerCounts,
      constraintPhrase: state.session.constraint_phrase || ""
    });
    const sessionId = state.session.session_id || crypto.randomUUID();
    state.session.session_id = sessionId;
    const validation = await api("/api/scorecard/validate", {
      method: "POST",
      body: JSON.stringify({ transcript, scorecard: coaching.coaching, mode: state.session.mode })
    });
    const attempt = {
      attempt: state.attempt,
      transcript,
      scorecard: validation.scorecard,
      inferenceSource: coaching.inferenceSource,
      durationSeconds: duration,
      fillerCount: Object.values(fillerCounts).reduce((sum, value) => sum + value, 0),
      createdAt: Date.now(),
      overallScore: validation.overallScore
    };

    let saved;
    if (state.attempt === 1) {
      const createdAt = Date.now();
      saved = {
        id: sessionId,
        mode: state.session.mode,
        goal: state.session.goal || "",
        category: state.session.category || "",
        heat: state.session.heat || "",
        prompt: state.session.prompt,
        constraint: state.session.constraint_phrase || "",
        createdAt,
        expiresAt: createdAt + Number(window.SPEAKEASY_CONFIG?.retentionDays || 30) * 86400000,
        retryUsed: false,
        latest: attempt,
        attempts: [attempt]
      };
      await saveSession(saved);
      sessionSaved = true;
      if (state.reservationId) {
        await consumeDailyReservation(state.reservationId);
        state.reservationId = null;
      }
    } else {
      saved = await appendRetry(sessionId, attempt);
      sessionSaved = true;
    }

    renderScorecard(saved, state.attempt);
    if (state.session.questionIndex !== undefined) {
      state.completed.add(state.session.questionIndex);
      state.unlocked = Math.min(14, Math.max(3, 3 + state.completed.size));
      renderQuestions();
    }
    await refreshUsage();
    toast("Your coaching report is ready.", "success");
  } catch (error) {
    if (state.attempt === 1 && !sessionSaved) await releaseReservation();
    toast(error.message, "error");
    $("#recording-status").textContent = "Analysis could not be completed. Your transcript remains available; try again.";
    $("#analyse-response").hidden = false;
  } finally {
    setBusy(button, false);
    state.busy = false;
  }
}

function highlightTranscript(transcript, annotations) {
  const matches = (annotations || [])
    .filter((item) => item.phrase && transcript.includes(item.phrase))
    .sort((a, b) => transcript.indexOf(a.phrase) - transcript.indexOf(b.phrase));
  let html = "";
  let cursor = 0;
  for (const item of matches) {
    const index = transcript.indexOf(item.phrase, cursor);
    if (index < 0) continue;
    html += escapeHtml(transcript.slice(cursor, index));
    html += `<mark title="${escapeHtml(item.reason)}">${escapeHtml(item.phrase)}</mark>`;
    cursor = index + item.phrase.length;
  }
  return html + escapeHtml(transcript.slice(cursor));
}

function renderScorecard(session, attemptNumber) {
  const latest = session.latest;
  const result = latest.scorecard;
  $("#session-panel").hidden = true;
  $("#scorecard-panel").hidden = false;
  $("#overall-score").textContent = Number(latest.overallScore).toFixed(1).replace(/\.0$/, "");
  const metrics = [
    ["Content", result.metrics.content],
    ["Structure", result.metrics.structure],
    ["Delivery & pacing", result.metrics.deliveryPacing],
    ["Confidence", result.metrics.confidence],
    ["Hook", result.metrics.hook],
    ["Filler control", result.metrics.fillerControl]
  ];
  $("#score-metrics").innerHTML = metrics.map(([label, score]) => `<div class="metric-row"><div class="metric-head"><span>${label}</span><strong>${score}</strong></div><div class="metric-track"><i style="width:${Math.max(0, Math.min(100, Number(score)))}%"></i></div></div>`).join("");
  $("#line-to-fix").textContent = `“${result.lineToFixQuote}”`;
  $("#line-diagnosis").textContent = result.lineToFixDiagnosis;
  $("#opening-rewrite").textContent = result.openingRewrite;
  $("#next-focus").textContent = result.nextFocus;
  const stanceBlock = $("#stance-block");
  stanceBlock.hidden = session.mode !== "hot-take";
  if (session.mode === "hot-take") {
    $("#stance-verdict").textContent = `${result.stanceClarity}/100 · ${result.stanceVerdict}`;
    $("#punchier-hook").textContent = result.punchierHookRewrite;
  }
  $("#annotated-transcript").innerHTML = highlightTranscript(latest.transcript, result.annotations);
  $("#score-source").textContent = sourceLabel(latest.inferenceSource);
  const first = session.attempts?.[0];
  const delta = attemptNumber === 2 && first ? latest.overallScore - first.overallScore : null;
  $("#score-delta").textContent = delta === null ? "" : `${delta >= 0 ? "+" : ""}${delta.toFixed(1).replace(/\.0$/, "")} pts from first attempt`;
  $("#retry-session").hidden = session.retryUsed || attemptNumber === 2;
  $("#retry-session").disabled = session.retryUsed || attemptNumber === 2;
  $("#finish-session").hidden = false;
  state.lastSavedSession = session;
  window.scrollTo({ top: $("#scorecard-panel").offsetTop - 18, behavior: "smooth" });
}

async function onRetry() {
  const saved = state.lastSavedSession;
  if (!saved || saved.retryUsed) return;
  state.attempt = 2;
  state.session.session_id = saved.id;
  $("#scorecard-panel").hidden = true;
  $("#session-panel").hidden = false;
  $("#live-transcript").value = "";
  setTranscript("");
  $("#start-recording").hidden = false;
  $("#start-recording").disabled = false;
  $("#stop-recording").disabled = true;
  $("#analyse-response").hidden = true;
  $("#timer-value").textContent = formatTime(state.duration);
  $("#recording-status").textContent = "Free retry · use the same prompt and focus on one improvement.";
  $("#start-recording").textContent = "Start free retry ●";
  await beginCapture({ hotPrep: state.session.mode === "hot-take", retry: true });
}

async function loadHistory() {
  const list = $("#history-list");
  list.innerHTML = '<div class="empty-state">Loading your sessions…</div>';
  try {
    const sessions = await listSessions(30);
    if (!sessions.length) {
      list.innerHTML = '<div class="empty-state">No completed sessions yet. Your practice history will appear here.</div>';
      return;
    }
    list.innerHTML = sessions.map((session) => {
      const latest = session.latest;
      const title = session.mode === "hot-take" ? `${session.category} · ${session.heat}` : session.goal;
      return `<article class="history-item"><div class="history-main"><div><span class="history-type">${session.mode === "hot-take" ? "HOT TAKE" : "STRUCTURED PRACTICE"}</span><h3>${escapeHtml(title)}</h3><p>${escapeHtml(session.prompt)}</p><span class="history-date">${new Date(session.createdAt).toLocaleString()}</span></div><div class="history-score"><strong>${Number(latest?.overallScore ?? 0).toFixed(1).replace(/\.0$/, "")}</strong><span>/100</span><small>${session.attempts.length} ${session.attempts.length === 1 ? "attempt" : "attempts"}</small></div></div><div class="history-actions"><button class="text-button" data-history-open="${session.id}">View feedback</button><button class="text-button destructive" data-history-delete="${session.id}">Delete</button></div></article>`;
    }).join("");
  } catch (error) {
    list.innerHTML = `<div class="empty-state">${escapeHtml(friendlyMessage(error.message))}</div>`;
  }
}

async function openHistorySession(sessionId) {
  try {
    const saved = await getSession(sessionId);
    if (!saved) throw new Error("That session is no longer available.");
    state.session = {
      session_id: saved.id,
      mode: saved.mode,
      goal: saved.goal,
      category: saved.category,
      heat: saved.heat,
      prompt: saved.prompt,
      constraint_phrase: saved.constraint
    };
    state.duration = saved.mode === "hot-take" ? 90 : 60;
    state.attempt = saved.attempts.length;
    state.lastSavedSession = saved;
    await switchView("history");
    renderScorecard(saved, saved.attempts.length);
  } catch (error) {
    toast(error.message, "error");
  }
}

async function deleteHistorySession(sessionId) {
  if (!confirm("Delete this practice session and its transcript?")) return;
  try {
    await deleteSession(sessionId);
    await loadHistory();
    toast("Session deleted.", "success");
  } catch (error) {
    toast(error.message, "error");
  }
}

function setupEvents() {
  $$(".nav-link").forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view)));
  $$(".goal-card").forEach((button) => button.addEventListener("click", () => {
    state.goal = button.dataset.goal;
    $$(".goal-card").forEach((card) => {
      const selected = card === button;
      card.classList.toggle("selected", selected);
      card.setAttribute("aria-pressed", String(selected));
    });
    $("#job-description-wrap").hidden = state.goal !== "Interview";
  }));
  $("#generate-questions").addEventListener("click", onGenerateQuestions);
  $("#question-list").addEventListener("click", (event) => {
    const button = event.target.closest("[data-question-index]");
    if (!button || button.disabled) return;
    const index = Number(button.dataset.questionIndex);
    const prompt = state.questions[index];
    openSession({ mode: "structured", goal: state.goal, prompt, questionIndex: index, constraint_phrase: "" });
  });
  $("#hot-category").addEventListener("change", () => {
    $("#custom-topic-wrap").hidden = $("#hot-category").value !== "Custom topic";
  });
  $$('input[name="heat"]').forEach((radio) => radio.addEventListener("change", () => {
    $$(".heat-option").forEach((item) => item.classList.toggle("selected", item.querySelector("input").checked));
  }));
  $("#generate-hot-take").addEventListener("click", onGenerateHotTake);
  $("#start-hot-take").addEventListener("click", () => {
    if (!state.hotTake) return;
    openSession({
      mode: "hot-take",
      category: state.hotTake.category,
      heat: state.hotTake.heat,
      prompt: state.hotTake.statement,
      constraint_phrase: state.hotTake.constraint
    });
    beginCapture({ hotPrep: true });
  });
  $("#start-recording").addEventListener("click", () => beginCapture({ hotPrep: state.session?.mode === "hot-take", retry: state.attempt === 2 }));
  $("#stop-recording").addEventListener("click", stopRecordingAndCoach);
  $("#analyse-response").addEventListener("click", analyseResponse);
  $("#live-transcript").addEventListener("input", (event) => {
    state.transcript = event.target.value;
    updateFillerCounts(state.transcript);
  });
  $("#retry-session").addEventListener("click", onRetry);
  $("#finish-session").addEventListener("click", () => {
    $("#scorecard-panel").hidden = true;
    state.session = null;
    if (state.view === "history") loadHistory();
    else if (state.view === "arena") $("#hot-takes").scrollIntoView({ behavior: "smooth", block: "start" });
    else window.scrollTo({ top: 0, behavior: "smooth" });
  });
  $("#close-session").addEventListener("click", async () => {
    await stopCapture(false);
    await releaseReservation();
    $("#session-panel").hidden = true;
  });
  $("#history-list").addEventListener("click", (event) => {
    const open = event.target.closest("[data-history-open]");
    const remove = event.target.closest("[data-history-delete]");
    if (open) openHistorySession(open.dataset.historyOpen);
    if (remove) deleteHistorySession(remove.dataset.historyDelete);
  });
  const dialog = $("#settings-dialog");
  $("#settings-toggle").addEventListener("click", () => dialog.showModal());
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
}

function init() {
  setupEvents();
  $("#job-description-wrap").hidden = false;
  $("#analyse-response").hidden = true;
  if (isAIReady()) setAIStatus("Firebase AI Logic ready", "ready");
  refreshUsage();
  // Listing prunes expired records during startup, so old history is removed
  // after the 30-day retention window without requiring a manual History visit.
  listSessions(1).catch((error) => console.warn("Local history cleanup could not run.", error));
  renderQuestions();
}

init();
