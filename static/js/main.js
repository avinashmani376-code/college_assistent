"use strict";

let chatInput, sendBtn, messagesArea, welcomeScreen, micBtn, transcriptPreview;
let chatHistory = [];
let recognition = null;
let isListening = false;

let cachedVoices = [];
function loadVoices() { cachedVoices = window.speechSynthesis ? speechSynthesis.getVoices() : []; }
if ("speechSynthesis" in window) {
  loadVoices();
  speechSynthesis.onvoiceschanged = loadVoices;
  try { const warm = new SpeechSynthesisUtterance(" "); warm.volume = 0; speechSynthesis.speak(warm); } catch (_) {}
}

function pickFemaleVoice(isTelugu) {
  if (!cachedVoices.length) loadVoices();
  const v = cachedVoices;
  if (isTelugu) {
    const te = v.find(x => /te[-_]?IN/i.test(x.lang)) || v.find(x => /telugu/i.test(x.name));
    if (te) return te;
    const hi = v.find(x => /hi[-_]?IN/i.test(x.lang) && /female|aditi|swara|kalpana/i.test(x.name));
    if (hi) return hi;
  }
  const preferred = ["Google UK English Female",
    "Microsoft Aria Online (Natural) - English (United States)",
    "Microsoft Jenny Online (Natural) - English (United States)",
    "Microsoft Zira - English (United States)",
    "Google US English","Samantha","Karen","Tessa","Victoria","Moira"];
  for (const name of preferred) {
    const hit = v.find(x => x.name === name || x.name.includes(name));
    if (hit) return hit;
  }
  const enFemale = v.find(x => /en[-_]/i.test(x.lang) && /female|woman|zira|aria|jenny|samantha|karen|tessa|victoria|moira/i.test(x.name));
  if (enFemale) return enFemale;
  return v.find(x => /en[-_]/i.test(x.lang)) || v[0] || null;
}

function stopSpeaking() { try { if ("speechSynthesis" in window) speechSynthesis.cancel(); } catch (_) {} }

function speak(text) {
  if (!("speechSynthesis" in window) || !text) return;
  stopSpeaking();
  const cleanText = String(text)
    .replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu, " ")
    .replace(/\*\*/g, "").replace(/[#_`>]/g, " ")
    .replace(/\s+/g, " ").trim();
  if (!cleanText) return;
  const isTelugu = /[\u0C00-\u0C7F]/.test(cleanText);
  const utterance = new SpeechSynthesisUtterance(cleanText);
  utterance.lang = isTelugu ? "te-IN" : "en-IN";
  const v = pickFemaleVoice(isTelugu);
  if (v) utterance.voice = v;
  utterance.rate = isTelugu ? 0.95 : 1.02;
  utterance.pitch = 1.25;
  utterance.volume = 1;
  speechSynthesis.speak(utterance);
}

function esc(str) { return String(str ?? "").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;"); }
function scrollBottom() { messagesArea.scrollTop = messagesArea.scrollHeight; }
function formatReply(text) { if (!text) return ""; return esc(text).replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>").replace(/\n/g, "<br>"); }
function aiAvatarHTML() {
  return `<div class="ai-avatar">
    <img src="/static/media/images/logo.png" alt="Ideal College"
         onerror="this.onerror=null;this.replaceWith(Object.assign(document.createElement('span'),{className:'ai-avatar-fallback',textContent:'IC'}))"/>
  </div>`;
}

function updateGreeting() {
  const el = document.getElementById("greetingText");
  const ds = document.getElementById("greetingDate");
  if (!el) return;
  const h = new Date().getHours();
  let g = "Good Morning";
  if (h >= 12 && h < 17) g = "Good Afternoon";
  else if (h >= 17 && h < 21) g = "Good Evening";
  else if (h >= 21 || h < 5) g = "Good Night";
  el.textContent = "🌟 " + g;
  if (ds) {
    const opt = { weekday: "long", day: "numeric", month: "short", year: "numeric" };
    ds.textContent = new Date().toLocaleDateString("en-IN", opt);
  }
}

function appendAIMessage(data) {
  const reply = data?.reply ?? "";
  const showImages = Boolean(data?.show_images);
  const showVideo = Boolean(data?.show_video);
  const images = Array.isArray(data?.images) ? data.images : [];
  const videoUrl = data?.video_url ?? "";
  let mediaHtml = "";
  if (showVideo && videoUrl) {
    mediaHtml = `<div class="media-frame"><video class="media-video" controls autoplay muted playsinline>
      <source src="${esc(videoUrl)}" type="video/mp4">Your browser does not support video.</video></div>`;
  }
  if (showImages && images.length) {
    const id = "slider-" + Date.now();
    mediaHtml = `<div class="media-frame"><div class="image-slider" id="${id}">
      <button class="slide-btn prev" onclick="changeSlide('${id}',-1)">&#8249;</button>
      <div class="slides">${images.map((s, i) => `<img src="${esc(s)}" class="slide${i === 0 ? " active" : ""}" alt="campus" loading="lazy"/>`).join("")}</div>
      <button class="slide-btn next" onclick="changeSlide('${id}',1)">&#8250;</button></div></div>`;
  }
  const div = document.createElement("div");
  div.className = "message ai-message";
  div.innerHTML = `${aiAvatarHTML()}
    <div class="message-bubble ai-bubble">
      <div class="ai-content">${formatReply(reply)}</div>${mediaHtml}
    </div>`;
  messagesArea.appendChild(div);
  speak(reply);
  scrollBottom();
}

function changeSlide(id, dir) {
  const slider = document.getElementById(id);
  if (!slider) return;
  const slides = slider.querySelectorAll(".slide");
  let cur = 0;
  slides.forEach((s, i) => { if (s.classList.contains("active")) cur = i; });
  slides[cur].classList.remove("active");
  let next = (cur + dir + slides.length) % slides.length;
  slides[next].classList.add("active");
}

function appendTyping() {
  const id = "typing-" + Date.now();
  const div = document.createElement("div");
  div.id = id;
  div.className = "message ai-message";
  div.innerHTML = `${aiAvatarHTML()}
    <div class="message-bubble ai-bubble">
      <div class="typing-indicator"><span></span><span></span><span></span></div>
    </div>`;
  messagesArea.appendChild(div);
  scrollBottom();
  return id;
}

function appendUserMessage(text) {
  const div = document.createElement("div");
  div.className = "message user-message";
  div.innerHTML = `<div class="message-bubble user-bubble">${esc(text)}</div>`;
  messagesArea.appendChild(div);
  scrollBottom();
}

function removeEl(id) { const el = document.getElementById(id); if (el) el.remove(); }

async function sendMessage() {
  const text = (chatInput.value || "").trim();
  if (!text) return;
  welcomeScreen.style.display = "none";
  messagesArea.style.display = "flex";
  appendUserMessage(text);
  chatHistory.push({ role: "user", content: text });
  chatInput.value = "";
  sendBtn.disabled = true;
  const typingId = appendTyping();
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, history: chatHistory.slice(-10) }),
    });
    let data;
    try { data = await res.json(); } catch { throw new Error("Invalid JSON"); }
    removeEl(typingId);
    if (res.ok && data.reply !== undefined) {
      appendAIMessage(data);
      chatHistory.push({ role: "assistant", content: data.reply });
    } else {
      appendAIMessage({ reply: data?.reply || "Something went wrong. Please try again." });
    }
  } catch (err) {
    console.error(err);
    removeEl(typingId);
    appendAIMessage({ reply: "Connection error. Please check your network and try again." });
  } finally {
    sendBtn.disabled = false;
    scrollBottom();
  }
}

function initSpeech() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return null;
  const rec = new SR();
  rec.lang = "en-IN";
  rec.interimResults = true;
  rec.continuous = false;
  rec.onresult = (e) => {
    let t = "";
    for (let i = e.resultIndex; i < e.results.length; i++) t += e.results[i][0].transcript;
    chatInput.value = t;
    if (transcriptPreview) transcriptPreview.textContent = t;
    const last = e.results[e.results.length - 1];
    if (last?.isFinal) {
      setTimeout(() => {
        if (transcriptPreview) transcriptPreview.textContent = "";
        sendMessage();
      }, 250);
    }
  };
  rec.onerror = rec.onend = () => {
    isListening = false;
    micBtn.classList.remove("active");
    if (transcriptPreview) transcriptPreview.textContent = "";
  };
  return rec;
}

function toggleVoice() {
  stopSpeaking();
  if (!recognition) recognition = initSpeech();
  if (!recognition) {
    appendAIMessage({ reply: "Voice input is not supported in this browser." });
    return;
  }
  if (isListening) {
    try { recognition.stop(); } catch (_) {}
    isListening = false;
    micBtn.classList.remove("active");
    if (transcriptPreview) transcriptPreview.textContent = "";
  } else {
    try {
      recognition.start();
      isListening = true;
      micBtn.classList.add("active");
      if (transcriptPreview) transcriptPreview.textContent = "Listening...";
    } catch {
      isListening = false;
      micBtn.classList.remove("active");
    }
  }
}

async function loadSidebarNews() {
  const list = document.getElementById("newsList");
  if (!list) return;
  try {
    const res = await fetch("/api/news-sidebar");
    const data = await res.json();
    const articles = data?.articles || [];
    if (!articles.length) {
      list.innerHTML = `<div class="news-loading">No updates available right now.</div>`;
      return;
    }
    list.innerHTML = articles.slice(0, 6).map(a => {
      const title = esc(a.title || "");
      const url = a.url || "#";
      const source = esc(a.source || "News");
      return `<a class="news-item" href="${esc(url)}" target="_blank" rel="noopener" title="Open full article">
        <div class="news-item-title">${title}</div>
        <div class="news-item-source">${source} · Read more →</div>
      </a>`;
    }).join("");
  } catch (err) {
    list.innerHTML = `<div class="news-loading">Unable to load updates.</div>`;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  // Always fresh on refresh / re-open
  try { sessionStorage.removeItem("ideal_chat"); } catch (_) {}
  try { localStorage.removeItem("ideal_chat"); } catch (_) {}

  chatInput = document.getElementById("chatInput");
  sendBtn = document.getElementById("sendBtn");
  messagesArea = document.getElementById("messagesArea");
  welcomeScreen = document.getElementById("welcomeScreen");
  micBtn = document.getElementById("micBtn");
  transcriptPreview = document.getElementById("transcriptPreview");

  sendBtn.addEventListener("click", sendMessage);
  micBtn.addEventListener("click", toggleVoice);

  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });

  document.querySelectorAll(".suggestion-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      chatInput.value = btn.dataset.text || btn.textContent.trim();
      sendMessage();
    });
  });

  // 📱 Mobile sidebar toggle
  const menuToggle = document.getElementById("menuToggle");
  const infoHub = document.getElementById("infoHub");
  const backdrop = document.getElementById("sidebarBackdrop");

  function closeSidebar() {
    if (infoHub) infoHub.classList.remove("open");
    if (backdrop) backdrop.classList.remove("active");
  }
  if (menuToggle && infoHub) {
    menuToggle.addEventListener("click", () => {
      infoHub.classList.toggle("open");
      if (backdrop) backdrop.classList.toggle("active");
    });
  }
  if (backdrop) backdrop.addEventListener("click", closeSidebar);

  // ✅ All sidebar tags (courses, facilities, timings) → send as user question to chat
  document.querySelectorAll("[data-ask]").forEach(el => {
    el.addEventListener("click", (e) => {
      if (e.target.closest("a")) return;
      const q = el.getAttribute("data-ask");
      if (!q) return;
      chatInput.value = q;
      sendMessage();
      closeSidebar();
    });
  });

  updateGreeting();
  setInterval(updateGreeting, 60000);
  loadSidebarNews();
  setInterval(loadSidebarNews, 5 * 60 * 1000);
});