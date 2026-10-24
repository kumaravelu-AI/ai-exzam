const chatBox = document.getElementById("chatBox");
const progressBox = document.getElementById("progressBox");
const storedStudentId = localStorage.getItem('ai-exzam-student-id');
const generatedStudentId = `student_${crypto.randomUUID().replaceAll('-', '').slice(0, 16)}`;
document.getElementById('studentId').value = storedStudentId || generatedStudentId;
if (!storedStudentId) localStorage.setItem('ai-exzam-student-id', generatedStudentId);
let busy = false;
let activeSession = null;
function setBusy(value) {
  busy = value;
  for (const id of ["sendBtn", "startBtn", "clarifyBtn"]) document.getElementById(id).disabled = value;
  document.querySelectorAll('.completion-actions button').forEach(button => { button.disabled = value; });
  document.getElementById("sendBtn").textContent = value ? "Thinking…" : "Send";
  chatBox.setAttribute("aria-busy", String(value));
}
function showProgress(data) {
  const session = data.session || activeSession || {};
  const progress = data.progress;
  progressBox.textContent = progress
    ? `Practice progress: ${progress.topic_mastery || 0}%\nQuestions practised: ${progress.questions_attempted || 0}\n${data.done ? "Lesson complete. Choose another topic when ready." : "Keep going — mistakes are part of learning."}`
    : `Lesson: ${(session.topic || "").replaceAll("_", " ")}\nMode: ${session.mode || "learning"}`;
}

function addMessage(role, text) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = text;
  chatBox.appendChild(div);
  chatBox.scrollTop = chatBox.scrollHeight;
}

async function postJSON(url, payload) {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await resp.json();
  if (!resp.ok) {
    throw new Error(data.detail || data.message || "Request failed");
  }
  return data;
}

async function getJSON(url) {
  const resp = await fetch(url);
  const data = await resp.json();
  if (!resp.ok) {
    throw new Error(data.detail || data.message || "Request failed");
  }
  return data;
}

function ensureTopicSelect() {
  const topicField = document.getElementById("topic");
  if (!topicField || topicField.tagName.toLowerCase() === "select") {
    return topicField;
  }

  const topicSelect = document.createElement("select");
  topicSelect.id = "topic";
  topicSelect.dataset.previousValue = topicField.value || "";
  topicField.replaceWith(topicSelect);
  return topicSelect;
}

function setTopicOptions(topics, selectedTopic) {
  const topicSelect = ensureTopicSelect();
  const topicStatus = document.getElementById("topicStatus");
  topicSelect.innerHTML = "";

  if (!topics.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No topics found";
    topicSelect.appendChild(option);
    if (topicStatus) {
      topicStatus.textContent = "No topics found in the selected subject and level.";
    }
    return;
  }

  topics.forEach((topic) => {
    const option = document.createElement("option");
    option.value = topic.id;
    option.textContent = topic.label || topic.id;
    if (topics.filter(item => item.label === topic.label).length > 1) {
      option.textContent += /^\d+_/.test(topic.id) ? ' — core lesson' : ' — extra practice';
    }
    if (!topic.has_questions) {
      option.textContent += " (no questions)";
    }
    topicSelect.appendChild(option);
  });

  const values = topics.map((topic) => topic.id);
  if (selectedTopic && values.includes(selectedTopic)) {
    topicSelect.value = selectedTopic;
  } else {
    topicSelect.value = values[0];
  }

  if (topicStatus) {
    topicStatus.textContent = `${topics.length} topic${topics.length === 1 ? "" : "s"} loaded from knowledgebase.`;
  }
}

async function loadTopics() {
  const topicSelect = ensureTopicSelect();
  const topicStatus = document.getElementById("topicStatus");
  const selectedTopic = topicSelect.value || topicSelect.dataset.previousValue || "";
  const subject = document.getElementById("subject").value.trim() || "science";
  const level = document.getElementById("level").value.trim() || "year6";
  const params = new URLSearchParams({ subject, level });

  topicSelect.innerHTML = "";
  const loading = document.createElement("option");
  loading.value = "";
  loading.textContent = "Loading topics...";
  topicSelect.appendChild(loading);
  if (topicStatus) {
    topicStatus.textContent = "Loading available topics...";
  }

  try {
    const data = await getJSON(`/api/knowledge/topics?${params.toString()}`);
    setTopicOptions((data.data && data.data.topics) || [], selectedTopic);
  } catch (err) {
    topicSelect.innerHTML = "";
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "Unable to load topics";
    topicSelect.appendChild(option);
    if (topicStatus) {
      topicStatus.textContent = "Unable to load topics. Check the backend is running.";
    }
    addMessage("bot", `Error loading topics: ${err.message}`);
  }
}

function getState() {
  return {
    student_id: document.getElementById("studentId").value.trim(),
    student_name: document.getElementById("studentName").value.trim(),
    subject: document.getElementById("subject").value.trim(),
    level: document.getElementById("level").value.trim(),
    topic: document.getElementById("topic").value.trim(),
    mode: document.getElementById("mode").value.trim(),
  };
}

function formatKnowledgeSummary(summary) {
  const data = summary || {};
  const errors = data.errors || [];
  return [
    data.message || "Knowledgebase generation completed.",
    "",
    `Files scanned: ${data.source_files_scanned || 0}`,
    `New files converted: ${data.new_files_converted || 0}`,
    `Already converted skipped: ${data.existing_files_skipped || 0}`,
    `Modified files detected: ${data.modified_files_detected || 0}`,
    `Topics created: ${data.topics_created || 0}`,
    `Draft files created: ${data.draft_files_created || 0}`,
    `Needs review: ${data.needs_review || 0}`,
    `Errors: ${data.errors_count || errors.length || 0}`,
    "",
    data.reminder || data.next_step || "Next step: Click Rebuild Index.",
  ].join("\n");
}

document.getElementById("rebuildBtn").addEventListener("click", async () => {
  try {
    const data = await postJSON("/api/admin/rebuild-index", {});
    addMessage("bot", `${data.message}\n${JSON.stringify(data.data, null, 2)}`);
  } catch (err) {
    addMessage("bot", `Error: ${err.message}`);
  }
});

document.getElementById("generateKnowledgeBtn").addEventListener("click", async () => {
  try {
    addMessage("bot", "Generating knowledgebase from source files...");
    const data = await postJSON("/api/knowledge/generate", {});
    addMessage("bot", formatKnowledgeSummary(data.data));
    await loadTopics();
  } catch (err) {
    addMessage("bot", `Error: ${err.message}`);
  }
});

async function startSession(state) {
  if (busy) return;
  state = {...state, student_name: state.student_name || document.getElementById('studentName').value.trim() || 'Student'};
  setBusy(true);
  try {
    const data = await postJSON("/api/session/start", state);
    activeSession = data.session;
    const fields = {studentId: 'student_id', studentName: 'student_name', subject: 'subject', level: 'level', mode: 'mode'};
    for (const [id, key] of Object.entries(fields)) document.getElementById(id).value = state[key] || '';
    await loadTopics();
    document.getElementById('topic').value = state.topic;
    chatBox.replaceChildren();
    document.getElementById('messageInput').value = '';
    document.getElementById('clarifyAsk').value = '';
    addMessage("bot", data.message);
    showProgress(data);
  } catch (err) {
    addMessage("bot", `Error: ${err.message}`);
  } finally { setBusy(false); }
}
document.getElementById("startBtn").addEventListener("click", () => startSession(getState()));

async function showCompletion(session) {
  const card = document.createElement('div');
  card.className = 'msg bot completion-actions';
  const heading = document.createElement('h3');
  heading.textContent = 'What would you like to do next? / அடுத்து என்ன செய்ய விரும்புகிறீர்கள்?';
  card.appendChild(heading);
  const note = document.createElement('p');
  note.className = 'muted';
  note.textContent = 'Retake starts this lesson again. Your previous progress is kept. / மீண்டும் பயிற்சி செய்யலாம். முந்தைய முன்னேற்றம் சேமிக்கப்படும்.';
  card.appendChild(note);
  const actions = document.createElement('div');
  actions.className = 'completion-buttons';
  const retake = document.createElement('button');
  retake.textContent = 'Retake training / மீண்டும் பயிற்சி';
  retake.disabled = busy;
  retake.addEventListener('click', () => startSession({...session}));
  actions.appendChild(retake);
  card.appendChild(actions);
  chatBox.appendChild(card);
  chatBox.scrollTop = chatBox.scrollHeight;
  try {
    const params = new URLSearchParams({subject: session.subject, level: session.level});
    const result = await getJSON(`/api/knowledge/topics?${params}`);
    // Treat core and extra-practice versions as one topic for forward navigation.
    const canonical = id => id.replace(/^\d+_/, '');
    const seen = new Set();
    const topics = result.data.topics.filter(topic => {
      const key = canonical(topic.id);
      if (!topic.has_questions || seen.has(key)) return false;
      seen.add(key); return true;
    });
    const current = topics.findIndex(topic => canonical(topic.id) === canonical(session.topic));
    const next = current >= 0 ? topics[current + 1] : null;
    if (next) {
      const nextButton = document.createElement('button');
      nextButton.className = 'primary';
      nextButton.textContent = `Next topic: ${next.label} / அடுத்த பாடம்`;
      nextButton.disabled = busy;
      nextButton.addEventListener('click', () => startSession({...session, topic: next.id}));
      actions.prepend(nextButton);
    } else {
      note.textContent += ' You reached the last topic. Choose any topic from the sidebar to continue. / கடைசிப் பாடத்தை முடித்துவிட்டீர்கள். வேறு பாடத்தைத் தேர்ந்தெடுக்கலாம்.';
    }
  } catch (err) {
    note.textContent += ' Next topic could not be loaded. You can select a topic from the sidebar.';
  }
  chatBox.scrollTop = chatBox.scrollHeight;
}

document.getElementById("sendBtn").addEventListener("click", async () => {
  if (busy) return;
  const input = document.getElementById("messageInput");
  const msg = input.value.trim();
  if (!msg) return;
  if (!activeSession) { addMessage("bot", "Choose a topic and press Start Session first."); return; }
  setBusy(true);
  addMessage("user", msg);
  input.value = "";
  try {
    const state = getState();
    const data = await postJSON("/api/chat/message", {
      student_id: activeSession.student_id,
      mode: activeSession.mode,
      message: msg,
    });
    addMessage("bot", data.message);
    activeSession = data.done ? null : data.session;
    showProgress(data);
    if (data.done) await showCompletion(data.session);
  } catch (err) {
    addMessage("bot", `Error: ${err.message}`);
    input.value = msg;
  } finally { setBusy(false); input.focus(); }
});

document.getElementById("clarifyBtn").addEventListener("click", async () => {
  if (busy || !activeSession) return;
  const ask = document.getElementById("clarifyAsk").value.trim();
  if (!ask) return;
  setBusy(true);
  try {
    const state = getState();
    const data = await postJSON("/api/chat/message", {
      student_id: activeSession.student_id,
      mode: activeSession.mode,
      message: ask,
    });
    addMessage("bot", data.message);
    activeSession = data.done ? null : data.session;
    showProgress(data);
    if (data.done) await showCompletion(data.session);
  } catch (err) {
    addMessage("bot", `Error: ${err.message}`);
  } finally { setBusy(false); }
});

document.getElementById("snapshotBtn").addEventListener("click", async () => {
  try {
    const studentId = document.getElementById("studentId").value.trim();
    const resp = await fetch(`/api/student/${encodeURIComponent(studentId)}/snapshot`);
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || "Load failed");
    progressBox.textContent = JSON.stringify(data.data, null, 2);
    addMessage("bot", "Student snapshot is loaded.\n\nமாணவர் நிலைத் தகவல் ஏற்றப்பட்டது.\n\nWhat would you like to check next?\nஅடுத்து நீங்கள் என்ன பார்க்க விரும்புகிறீர்கள்?");
  } catch (err) {
    addMessage("bot", `Error: ${err.message}`);
  }
});

document.getElementById("subject").addEventListener("change", loadTopics);
document.getElementById("level").addEventListener("change", loadTopics);
document.getElementById("reloadTopicsBtn").addEventListener("click", loadTopics);
loadTopics();
getJSON('/api/status').then(status => {
  if (!status.admin_enabled) {
    document.getElementById('manageContent').hidden = true;
    document.getElementById('studentId').readOnly = true;
  }
  document.getElementById('tutorStatus').textContent = status.mode === 'demo'
    ? 'Demo mode — limited answer checking. AI reasoning is not connected.'
    : 'AI tutor • English & Tamil • Ask questions in your own words';
}).catch(() => { document.getElementById('tutorStatus').textContent = 'Unable to reach the tutor.'; });

document.getElementById("messageInput").addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault(); document.getElementById("sendBtn").click();
  }
});
chatBox.setAttribute("role", "log");
chatBox.setAttribute("aria-live", "polite");
addMessage("bot", "Welcome! Choose a topic and press Start Session. Answer in your own words, in English or Tamil. You can ask for an example or a simpler explanation anytime.\n\nவணக்கம்! ஒரு பாடத்தைத் தேர்ந்தெடுத்து Start Session பொத்தானை அழுத்துங்கள். உங்கள் சொந்த வார்த்தைகளில் தமிழிலோ ஆங்கிலத்திலோ பதில் சொல்லலாம். புரியவில்லை என்றால் உதவி கேளுங்கள்.");

// Recover the end-of-lesson choices after a refresh without restarting training.
const initialStudentId = getState().student_id;
getJSON(`/api/student/${encodeURIComponent(initialStudentId)}/snapshot`).then(data => {
  const session = data.data && data.data.session;
  if (!busy && !activeSession && getState().student_id === initialStudentId &&
      session && ['completed', 'exam_completed'].includes(session.topic_status)) {
    addMessage('bot', 'Your previous session is complete. Continue with another topic or practise again. / முந்தைய பயிற்சி முடிந்துவிட்டது. அடுத்த பாடத்தைத் தொடரலாம் அல்லது மீண்டும் பயிற்சி செய்யலாம்.');
    return showCompletion(session);
  }
}).catch(() => {});
