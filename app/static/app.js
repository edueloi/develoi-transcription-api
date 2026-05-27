const state = {
  messages: [],
  selectedAction: "summary",
  lastTranscription: "",
  lastLanguage: "",
  defaultVoice: "",
  voiceOptions: [],
  settingsVisible: true,
};

const actionTemplates = {
  summary: "Resuma a transcrição em português do Brasil, destacando pontos principais e próximos passos.",
  detail: "Detalhe a transcrição em português do Brasil, organizando os pontos em tópicos claros e objetivos.",
  explain: "Explique a transcrição em português do Brasil de forma didática, contextualizando o que foi dito.",
  custom: "",
};

const $ = (id) => document.getElementById(id);

const el = {
  apiStatus: $("apiStatus"),
  apiDot: $("apiDot"),
  whisperModel: $("whisperModel"),
  whisperDot: $("whisperDot"),
  ollamaStatus: $("ollamaStatus"),
  ollamaDot: $("ollamaDot"),
  ollamaModel: $("ollamaModel"),
  modelDot: $("modelDot"),
  ttsStatus: $("ttsStatus"),
  ttsDot: $("ttsDot"),
  chatModelInput: $("chatModelInput"),
  systemPromptInput: $("systemPromptInput"),
  chatVoiceSelect: $("chatVoiceSelect"),
  chatStream: $("chatStream"),
  chatInput: $("chatInput"),
  clearChatButton: $("clearChatButton"),
  settingsToggle: $("settingsToggle"),
  chatSettingsBar: $("chatSettingsBar"),
  useTranscriptButton: $("useTranscriptButton"),
  sendChatButton: $("sendChatButton"),
  sendChatVoiceButton: $("sendChatVoiceButton"),
  uploadArea: $("uploadArea"),
  audioFileInput: $("audioFileInput"),
  transcribeButton: $("transcribeButton"),
  transcribeAnalyzeButton: $("transcribeAnalyzeButton"),
  fileBadge: $("fileBadge"),
  selectedFileName: $("selectedFileName"),
  detectedLanguage: $("detectedLanguage"),
  transcriptionOutput: $("transcriptionOutput"),
  copyTranscriptBtn: $("copyTranscriptBtn"),
  analysisModelInput: $("analysisModelInput"),
  temperatureInput: $("temperatureInput"),
  analysisInstructionInput: $("analysisInstructionInput"),
  analyzeButton: $("analyzeButton"),
  analysisOutput: $("analysisOutput"),
  copyAnalysisBtn: $("copyAnalysisBtn"),
  ttsVoiceSelect: $("ttsVoiceSelect"),
  ttsSpeedInput: $("ttsSpeedInput"),
  ttsSpeedRange: $("ttsSpeedRange"),
  ttsSpeedLabel: $("ttsSpeedLabel"),
  voiceGrid: $("voiceGrid"),
  ttsTextInput: $("ttsTextInput"),
  ttsSpeakButton: $("ttsSpeakButton"),
  ttsUseTranscriptButton: $("ttsUseTranscriptButton"),
  ttsUseAnalysisButton: $("ttsUseAnalysisButton"),
  ttsResultMeta: $("ttsResultMeta"),
  ttsAudioPlayer: $("ttsAudioPlayer"),
  ttsDownloadLink: $("ttsDownloadLink"),
  toast: $("toast"),
  segments: Array.from(document.querySelectorAll(".seg-btn")),
  tabBtns: Array.from(document.querySelectorAll(".tab-btn")),
};

let toastTimer;

function showToast(message, type = "") {
  el.toast.textContent = message;
  el.toast.className = "toast show" + (type ? " " + type : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.toast.classList.remove("show"), 3200);
}

function setBusy(buttons, busy) {
  buttons.forEach((button) => {
    if (button) button.disabled = busy;
  });
}

function normalizeError(error) {
  if (typeof error === "string") return error;
  if (error?.detail) {
    return typeof error.detail === "string" ? error.detail : JSON.stringify(error.detail, null, 2);
  }
  return JSON.stringify(error, null, 2);
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) throw data;
  return data;
}

function setDot(dot, nextState) {
  dot.className = "pill-dot " + nextState;
}

function switchTab(name) {
  el.tabBtns.forEach((button) => button.classList.toggle("active", button.dataset.tab === name));
  document.querySelectorAll(".tab-content").forEach((tab) => {
    tab.classList.toggle("active", tab.id === "tab-" + name);
  });
}

function toggleSettings() {
  state.settingsVisible = !state.settingsVisible;
  el.chatSettingsBar.style.display = state.settingsVisible ? "" : "none";
}

function renderChat() {
  el.chatStream.innerHTML = "";

  if (!state.messages.length) {
    el.chatStream.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">IA</div>
        <strong>Nenhuma mensagem ainda</strong>
        <span>Envie uma pergunta ou use a transcrição como contexto.</span>
      </div>`;
    return;
  }

  state.messages.forEach((message) => {
    const wrap = document.createElement("div");
    wrap.className = `message message-${message.role}`;

    const role = document.createElement("span");
    role.className = "message-role";
    role.textContent =
      message.role === "assistant"
        ? "IA"
        : message.role === "user"
          ? "Você"
          : "Sistema";

    const body = document.createElement("div");
    body.className = "message-body";
    body.textContent = message.content;

    wrap.appendChild(role);
    wrap.appendChild(body);

    if (message.audioUrl) {
      const meta = document.createElement("div");
      meta.className = "message-meta";
      meta.textContent = `Áudio gerado · ${message.voice || state.defaultVoice || ""}`;

      const audio = document.createElement("audio");
      audio.className = "message-audio";
      audio.controls = true;
      audio.preload = "none";
      audio.src = message.audioUrl;

      wrap.appendChild(meta);
      wrap.appendChild(audio);
    }

    el.chatStream.appendChild(wrap);
  });

  el.chatStream.scrollTop = el.chatStream.scrollHeight;
}

function setSelectedAction(action) {
  state.selectedAction = action;
  el.segments.forEach((segment) => segment.classList.toggle("active", segment.dataset.action === action));
  if (action !== "custom") {
    el.analysisInstructionInput.value = actionTemplates[action];
  }
}

function getChatPayload() {
  const systemPrompt = el.systemPromptInput.value.trim();
  const messages = [];

  if (systemPrompt) {
    messages.push({ role: "system", content: systemPrompt });
  }

  state.messages.forEach((message) => {
    if (message.role === "user" || message.role === "assistant") {
      messages.push({ role: message.role, content: message.content });
    }
  });

  return messages;
}

function getVoiceSettings() {
  const speedValue = Number(el.ttsSpeedInput.value || 1);
  return {
    voice: el.ttsVoiceSelect.value || el.chatVoiceSelect.value || state.defaultVoice || null,
    speed: Number.isFinite(speedValue) ? speedValue : 1,
  };
}

function renderVoiceCards(selectedId) {
  if (!el.voiceGrid) return;
  el.voiceGrid.innerHTML = "";

  if (!state.voiceOptions.length) {
    el.voiceGrid.innerHTML = '<div class="voice-loading">Nenhuma voz disponível.</div>';
    return;
  }

  state.voiceOptions.forEach((voice) => {
    const card = document.createElement("div");
    card.className = "voice-card" + (voice.id === selectedId ? " selected" : "");
    card.dataset.voiceId = voice.id;

    const name = voice.label.split(" (")[0];
    const genderIcon = voice.gender === "feminino" ? "♀" : "♂";
    const genderClass = voice.gender === "feminino" ? "voice-badge-female" : "voice-badge-male";

    card.innerHTML = `
      <div class="voice-card-name">${name}</div>
      <div class="voice-card-badges">
        <span class="voice-badge ${genderClass}">${genderIcon} ${voice.gender}</span>
        <span class="voice-badge voice-badge-locale">${voice.locale}</span>
      </div>`;

    card.addEventListener("click", () => selectVoice(voice.id));
    el.voiceGrid.appendChild(card);
  });
}

function selectVoice(voiceId) {
  el.ttsVoiceSelect.value = voiceId;
  if (el.chatVoiceSelect) el.chatVoiceSelect.value = voiceId;
  document.querySelectorAll(".voice-card").forEach((c) => {
    c.classList.toggle("selected", c.dataset.voiceId === voiceId);
  });
}

function populateVoiceSelect(select, selectedValue) {
  select.innerHTML = "";
  state.voiceOptions.forEach((voice) => {
    const option = document.createElement("option");
    option.value = voice.id;
    option.textContent = voice.label;
    option.selected = voice.id === selectedValue;
    select.appendChild(option);
  });
}

function setVoiceOptions(voices) {
  state.voiceOptions = Array.isArray(voices) ? voices : [];
  if (!state.voiceOptions.length) return;

  const defaultOption = state.voiceOptions.find((v) => v.is_default) || state.voiceOptions[0];
  const selectedValue = state.defaultVoice || defaultOption.id;

  populateVoiceSelect(el.ttsVoiceSelect, selectedValue);
  if (el.chatVoiceSelect) populateVoiceSelect(el.chatVoiceSelect, selectedValue);
  renderVoiceCards(selectedValue);
}

function setVoiceResult(speech, autoplay = false) {
  if (!speech?.audio_url) return;

  el.ttsResultMeta.textContent =
    `Voz: ${speech.voice} · Duração: ${speech.duration_seconds}s · Taxa: ${speech.sample_rate} Hz · Tamanho: ${speech.size_bytes} bytes`;
  el.ttsResultMeta.classList.remove("placeholder");

  el.ttsAudioPlayer.src = speech.audio_url;
  el.ttsAudioPlayer.style.display = "";

  el.ttsDownloadLink.href = speech.audio_url;
  el.ttsDownloadLink.download = speech.audio_url.split("/").pop() || "fala.wav";
  el.ttsDownloadLink.style.display = "inline-flex";

  if (autoplay) {
    el.ttsAudioPlayer.play().catch(() => {});
  }
}

function showTyping() {
  hideTyping();
  const wrap = document.createElement("div");
  wrap.className = "typing-indicator";
  wrap.id = "typingIndicator";
  const bubble = document.createElement("div");
  bubble.className = "typing-bubble";
  bubble.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';
  wrap.appendChild(bubble);
  el.chatStream.appendChild(wrap);
  el.chatStream.scrollTop = el.chatStream.scrollHeight;
}

function hideTyping() {
  const existing = document.getElementById("typingIndicator");
  if (existing) existing.remove();
}

function fillTtsText(text) {
  el.ttsTextInput.value = text;
  switchTab("voice");
  el.ttsTextInput.focus();
}

async function loadStatus() {
  setDot(el.apiDot, "loading");
  try {
    const health = await requestJson("/health");
    el.apiStatus.textContent = "online";
    setDot(el.apiDot, "online");
    el.whisperModel.textContent = health.whisper_model || "—";
    setDot(el.whisperDot, "online");
    el.ollamaModel.textContent = health.ollama_default_model || "—";
    setDot(el.modelDot, "online");
    if (!el.chatModelInput.value) el.chatModelInput.value = health.ollama_default_model || "";
    if (!el.analysisModelInput.value) el.analysisModelInput.value = health.ollama_default_model || "";
  } catch {
    el.apiStatus.textContent = "erro";
    setDot(el.apiDot, "offline");
  }

  setDot(el.ollamaDot, "loading");
  try {
    const ollama = await requestJson("/ai/health");
    el.ollamaStatus.textContent = `${ollama.model_count} modelo${ollama.model_count !== 1 ? "s" : ""}`;
    setDot(el.ollamaDot, "online");
  } catch {
    el.ollamaStatus.textContent = "offline";
    setDot(el.ollamaDot, "offline");
  }

  setDot(el.ttsDot, "loading");
  try {
    const tts = await requestJson("/tts/health");
    state.defaultVoice = tts.default_voice || "";
    el.ttsStatus.textContent = tts.voice_ready ? "pronta" : "1º download";
    setDot(el.ttsDot, tts.voice_ready ? "online" : "loading");

    const voices = await requestJson("/tts/voices");
    setVoiceOptions(voices.voices || []);
  } catch {
    el.ttsStatus.textContent = "erro";
    setDot(el.ttsDot, "offline");
  }
}

async function sendChat(withAudio = false) {
  const message = el.chatInput.value.trim();
  if (!message) {
    showToast("Digite uma mensagem antes de enviar.");
    return;
  }

  state.messages.push({ role: "user", content: message });
  renderChat();
  el.chatInput.value = "";

  const buttons = [el.sendChatButton, el.sendChatVoiceButton, el.clearChatButton];
  const activeButton = withAudio ? el.sendChatVoiceButton : el.sendChatButton;
  setBusy(buttons, true);
  activeButton.classList.add("loading");
  showTyping();

  try {
    const payload = {
      model: el.chatModelInput.value.trim() || null,
      messages: getChatPayload(),
    };

    let response;
    if (withAudio) {
      const voiceSettings = {
        ...getVoiceSettings(),
        voice: el.chatVoiceSelect.value || state.defaultVoice || null,
      };
      response = await requestJson("/ai/chat-and-speak", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...payload,
          voice: voiceSettings.voice,
          speed: voiceSettings.speed,
        }),
      });

      state.messages.push({
        role: "assistant",
        content: response.generation?.content || "",
        audioUrl: response.speech?.audio_url || "",
        voice: response.speech?.voice || voiceSettings.voice,
      });

      setVoiceResult(response.speech, true);
      switchTab("voice");
      showToast("Resposta com áudio gerada.", "success");
    } else {
      response = await requestJson("/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      state.messages.push({ role: "assistant", content: response.content || "" });
    }
  } catch (error) {
    state.messages.push({
      role: "system",
      content: `Erro ao consultar a IA:\n${normalizeError(error)}`,
    });
    showToast("Falha ao consultar a IA.", "error");
  } finally {
    hideTyping();
    setBusy(buttons, false);
    activeButton.classList.remove("loading");
    renderChat();
  }
}

function onFileSelected() {
  const file = el.audioFileInput.files?.[0];
  if (!file) return;

  el.fileBadge.style.display = "flex";
  el.selectedFileName.textContent = file.name;
  el.detectedLanguage.style.display = "none";
  state.lastLanguage = "";
}

function updateLangBadge(language) {
  if (!language) return;
  el.detectedLanguage.textContent = language.toUpperCase();
  el.detectedLanguage.style.display = "inline";
}

async function transcribeAudio() {
  const file = el.audioFileInput.files?.[0];
  if (!file) {
    showToast("Selecione um arquivo de áudio.");
    return null;
  }

  const formData = new FormData();
  formData.append("file", file);

  setBusy([el.transcribeButton, el.transcribeAnalyzeButton], true);
  el.transcribeButton.classList.add("loading");

  try {
    const response = await requestJson("/transcribe", { method: "POST", body: formData });
    state.lastTranscription = response.text || "";
    state.lastLanguage = response.language || "";
    el.transcriptionOutput.value = state.lastTranscription;
    updateLangBadge(state.lastLanguage);
    showToast("Transcrição concluída.", "success");
    return response;
  } catch (error) {
    showToast(normalizeError(error), "error");
    return null;
  } finally {
    setBusy([el.transcribeButton, el.transcribeAnalyzeButton], false);
    el.transcribeButton.classList.remove("loading");
  }
}

async function analyzeTranscription() {
  const text = el.transcriptionOutput.value.trim();
  if (!text) {
    showToast("Faça a transcrição ou cole um texto antes de analisar.");
    return;
  }

  const instruction = el.analysisInstructionInput.value.trim();
  if (!instruction) {
    showToast("Informe uma instrução para a análise.");
    return;
  }

  setBusy([el.analyzeButton], true);
  el.analyzeButton.classList.add("loading");
  el.analysisOutput.textContent = "Gerando análise…";
  el.analysisOutput.classList.add("placeholder");

  try {
    const response = await requestJson("/ai/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: el.analysisModelInput.value.trim() || null,
        prompt: `${instruction}\n\nTranscrição:\n${text}`,
        system: "Responda em português do Brasil.",
        temperature: Number(el.temperatureInput.value || 0.2),
      }),
    });

    el.analysisOutput.textContent = response.content || "";
    el.analysisOutput.classList.remove("placeholder");
    showToast("Análise concluída.", "success");
  } catch (error) {
    el.analysisOutput.textContent = `Erro:\n${normalizeError(error)}`;
    el.analysisOutput.classList.remove("placeholder");
    showToast("Falha ao gerar análise.", "error");
  } finally {
    setBusy([el.analyzeButton], false);
    el.analyzeButton.classList.remove("loading");
  }
}

async function transcribeAndAnalyze() {
  const file = el.audioFileInput.files?.[0];
  if (!file) {
    showToast("Selecione um arquivo de áudio.");
    return;
  }

  const instruction = el.analysisInstructionInput.value.trim();
  if (!instruction) {
    switchTab("analysis");
    showToast("Informe uma instrução para a análise antes de continuar.");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);
  formData.append("instruction", instruction);

  const model = el.analysisModelInput.value.trim();
  if (model) formData.append("model", model);
  formData.append("temperature", String(Number(el.temperatureInput.value || 0.2)));

  setBusy([el.transcribeButton, el.transcribeAnalyzeButton, el.analyzeButton], true);
  el.transcribeAnalyzeButton.classList.add("loading");

  try {
    const response = await requestJson("/ai/transcribe-and-generate", {
      method: "POST",
      body: formData,
    });

    state.lastTranscription = response.transcription.text || "";
    state.lastLanguage = response.transcription.language || "";
    el.transcriptionOutput.value = state.lastTranscription;
    updateLangBadge(state.lastLanguage);
    el.analysisOutput.textContent = response.generation.content || "";
    el.analysisOutput.classList.remove("placeholder");
    switchTab("analysis");
    showToast("Transcrição e análise concluídas.", "success");
  } catch (error) {
    el.analysisOutput.textContent = `Erro:\n${normalizeError(error)}`;
    el.analysisOutput.classList.remove("placeholder");
    showToast("Falha ao processar o áudio com a IA.", "error");
  } finally {
    setBusy([el.transcribeButton, el.transcribeAnalyzeButton, el.analyzeButton], false);
    el.transcribeAnalyzeButton.classList.remove("loading");
  }
}

async function speakText() {
  const text = el.ttsTextInput.value.trim();
  if (!text) {
    showToast("Digite algum texto para gerar o áudio.");
    return;
  }

  const voiceSettings = getVoiceSettings();
  setBusy([el.ttsSpeakButton], true);
  el.ttsSpeakButton.classList.add("loading");

  try {
    const response = await requestJson("/tts/synthesize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        voice: voiceSettings.voice,
        speed: voiceSettings.speed,
      }),
    });

    setVoiceResult(response, true);
    showToast("Áudio gerado com sucesso.", "success");
  } catch (error) {
    el.ttsResultMeta.textContent = `Erro:\n${normalizeError(error)}`;
    el.ttsResultMeta.classList.remove("placeholder");
    showToast("Falha ao gerar áudio.", "error");
  } finally {
    setBusy([el.ttsSpeakButton], false);
    el.ttsSpeakButton.classList.remove("loading");
  }
}

function copyText(text, label) {
  if (!text) {
    showToast("Nenhum conteúdo para copiar.");
    return;
  }

  navigator.clipboard.writeText(text).then(
    () => showToast(`${label} copiado.`, "success"),
    () => showToast("Falha ao copiar.", "error"),
  );
}

function bindEvents() {
  el.sendChatButton.addEventListener("click", () => sendChat(false));
  el.sendChatVoiceButton.addEventListener("click", () => sendChat(true));
  el.clearChatButton.addEventListener("click", () => {
    state.messages = [];
    renderChat();
  });

  el.settingsToggle.addEventListener("click", toggleSettings);
  if (el.chatVoiceSelect) el.chatVoiceSelect.addEventListener("change", () => selectVoice(el.chatVoiceSelect.value));
  el.ttsVoiceSelect.addEventListener("change", () => selectVoice(el.ttsVoiceSelect.value));

  if (el.ttsSpeedRange) {
    el.ttsSpeedRange.addEventListener("input", () => {
      const v = parseFloat(el.ttsSpeedRange.value).toFixed(2).replace(/\.?0+$/, "") + "×";
      el.ttsSpeedLabel.textContent = v;
      el.ttsSpeedInput.value = el.ttsSpeedRange.value;
    });
  }
  el.useTranscriptButton.addEventListener("click", () => {
    const text = el.transcriptionOutput.value.trim();
    if (!text) {
      showToast("Não há transcrição disponível.");
      return;
    }

    el.chatInput.value = `Use a transcrição abaixo como contexto e me responda:\n\n${text}`;
    el.chatInput.focus();
  });

  el.chatInput.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      sendChat(false);
    }
  });

  el.audioFileInput.addEventListener("change", onFileSelected);
  el.transcribeButton.addEventListener("click", transcribeAudio);
  el.transcribeAnalyzeButton.addEventListener("click", transcribeAndAnalyze);
  el.analyzeButton.addEventListener("click", analyzeTranscription);

  el.copyTranscriptBtn.addEventListener("click", () => copyText(el.transcriptionOutput.value.trim(), "Transcrição"));
  el.copyAnalysisBtn.addEventListener("click", () => copyText(el.analysisOutput.textContent.trim(), "Resultado"));

  el.ttsUseTranscriptButton.addEventListener("click", () => {
    const text = el.transcriptionOutput.value.trim();
    if (!text) {
      showToast("Não há transcrição disponível.");
      return;
    }
    fillTtsText(text);
  });

  el.ttsUseAnalysisButton.addEventListener("click", () => {
    const text = el.analysisOutput.classList.contains("placeholder")
      ? ""
      : el.analysisOutput.textContent.trim();

    if (!text) {
      showToast("Ainda não existe resultado para ler.");
      return;
    }
    fillTtsText(text);
  });

  el.ttsSpeakButton.addEventListener("click", speakText);

  el.segments.forEach((segment) => {
    segment.addEventListener("click", () => setSelectedAction(segment.dataset.action));
  });

  el.tabBtns.forEach((button) => {
    button.addEventListener("click", () => switchTab(button.dataset.tab));
  });

  const uploadArea = el.uploadArea;
  uploadArea.addEventListener("dragover", (event) => {
    event.preventDefault();
    uploadArea.classList.add("dragover");
  });
  uploadArea.addEventListener("dragleave", () => uploadArea.classList.remove("dragover"));
  uploadArea.addEventListener("drop", (event) => {
    event.preventDefault();
    uploadArea.classList.remove("dragover");

    const file = event.dataTransfer.files?.[0];
    if (file && file.type.startsWith("audio/")) {
      const dataTransfer = new DataTransfer();
      dataTransfer.items.add(file);
      el.audioFileInput.files = dataTransfer.files;
      onFileSelected();
      return;
    }

    showToast("Solte apenas arquivos de áudio.", "error");
  });
}

function init() {
  bindEvents();
  setSelectedAction("summary");
  renderChat();
  loadStatus();
}

init();
