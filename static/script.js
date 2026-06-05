/* ── Student Academic Assistant Chatbot — Frontend Logic ───────────────── */

// Generate a simple session ID (persisted per browser tab)
const SESSION_ID = `sess_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;

const chatWindow = document.getElementById("chatWindow");
const userInput  = document.getElementById("userInput");
const sendBtn    = document.getElementById("sendBtn");
const resetBtn   = document.getElementById("resetBtn");
const subtitle   = document.getElementById("headerSubtitle");

let isLocked   = false;   // prevents sending while bot is "typing"
let catRunning = false;   // true while a CAT is in progress

// ── Helpers ─────────────────────────────────────────────────────────────

function scrollToBottom() {
  chatWindow.scrollTo({ top: chatWindow.scrollHeight, behavior: "smooth" });
}

function setLocked(val) {
  isLocked = val;
  sendBtn.disabled = val;
  userInput.disabled = val;
  if (val) {
    subtitle.textContent = "Typing…";
    subtitle.style.color = "var(--hint)";
  } else {
    subtitle.textContent = "Online";
    subtitle.style.color = "var(--correct)";
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ── Message renderers ────────────────────────────────────────────────────

/** Append a user bubble */
function appendUserBubble(text) {
  const msg = document.createElement("div");
  msg.className = "message user";
  msg.innerHTML = `
    <div class="bubble" role="listitem" aria-label="You: ${text}">${escapeHtml(text)}</div>
    <div class="bubble-avatar" aria-hidden="true">🧑</div>
  `;
  chatWindow.appendChild(msg);
  scrollToBottom();
}

/** Append a bot text bubble */
function appendBotBubble(text, extraClass = "") {
  const msg = document.createElement("div");
  msg.className = "message bot";
  msg.setAttribute("role", "listitem");
  const bubbleClass = `bubble${extraClass ? " " + extraClass : ""}`;
  msg.innerHTML = `
    <div class="bubble-avatar" aria-hidden="true">🎓</div>
    <div class="${bubbleClass}">${text}</div>
  `;
  chatWindow.appendChild(msg);
  scrollToBottom();
}

/** Show a temporary typing indicator, then remove it */
async function showTyping(durationMs = 600) {
  const el = document.createElement("div");
  el.className = "typing-indicator";
  el.setAttribute("aria-label", "Bot is typing");
  el.setAttribute("role", "status");
  el.innerHTML = `
    <div class="typing-dot"></div>
    <div class="typing-dot"></div>
    <div class="typing-dot"></div>
  `;
  chatWindow.appendChild(el);
  scrollToBottom();
  await sleep(durationMs);
  el.remove();
}

/** Append a question card */
function appendQuestionCard(data) {
  catRunning = true;
  const card = document.createElement("div");
  card.className = "question-card";
  card.setAttribute("role", "listitem");
  card.setAttribute("aria-label", `Question ${data.number} of ${data.total}`);

  const optionsHtml = Object.entries(data.options).map(([key, val]) => `
    <button class="option-btn" data-key="${key}" aria-label="Option ${key}: ${val}">
      <span class="option-key">${key}.</span>
      <span>${escapeHtml(val)}</span>
    </button>
  `).join("");

  card.innerHTML = `
    <div class="q-header">
      <span class="q-badge">❓ QUESTION ${data.number}</span>
      <span class="q-progress">${data.number} / ${data.total}</span>
    </div>
    <p class="q-text">${escapeHtml(data.question)}</p>
    <div class="q-options">${optionsHtml}</div>
    <div class="q-hint">
      <span>💡</span>
      <span>${escapeHtml(data.hint)}</span>
    </div>
  `;

  // Clicking an option button auto-sends the answer
  card.querySelectorAll(".option-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      if (isLocked) return;
      const key = btn.dataset.key;
      // Disable all buttons on this card after selection
      card.querySelectorAll(".option-btn").forEach(b => b.disabled = true);
      btn.style.background = "var(--accent)";
      btn.style.color = "#fff";
      sendMessage(key);
    });
  });

  chatWindow.appendChild(card);
  scrollToBottom();
}

/** Countdown bubble: counts down from 5 then fires the CAT start follow-up */
async function appendCountdown() {
  const el = document.createElement("div");
  el.className = "countdown-bubble";
  el.setAttribute("role", "status");
  el.setAttribute("aria-live", "polite");
  el.innerHTML = `
    <span class="countdown-number" id="cdNum">5</span>
    <p class="countdown-label">seconds until CAT starts…</p>
  `;
  chatWindow.appendChild(el);
  scrollToBottom();

  for (let i = 5; i >= 1; i--) {
    document.getElementById("cdNum").textContent = i;
    await sleep(1000);
  }
  el.remove();
  // Auto-trigger the server to begin the CAT
  await sendMessage("__start_cat__", true);
}

// ── Core send function ───────────────────────────────────────────────────

/**
 * @param {string}  msg         - message text to send
 * @param {boolean} silent      - if true, don't append a user bubble
 */
async function sendMessage(msg, silent = false) {
  if (!msg.trim()) return;
  if (isLocked) return;

  setLocked(true);

  if (!silent) {
    appendUserBubble(msg);
  }

  // Typing delay varies with message length for realism
  const typingMs = Math.min(300 + msg.length * 8, 900);
  await showTyping(typingMs);

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: SESSION_ID, message: msg })
    });

    const data = await res.json();

    for (const resp of data.responses) {
      // Small stagger between consecutive bot messages
      if (chatWindow.lastElementChild) await sleep(180);

      switch (resp.type) {
        case "question":
          appendQuestionCard(resp);
          break;

        case "countdown":
          // Special sentinel: trigger countdown animation
          appendCountdown();
          // Return early — countdown fires the next request itself
          setLocked(false);
          return;

        case "score":
          appendBotBubble(resp.text, "score");
          break;

        case "review":
          appendBotBubble(resp.text, "review");
          break;

        default:
          appendBotBubble(resp.text);
      }
    }

    // If the session finished, lock input permanently
    const lastResp = data.responses[data.responses.length - 1];
    if (lastResp && lastResp.text && lastResp.text.includes("Thank you")) {
      catRunning = false;
      lockSession();
    }

  } catch (err) {
    appendBotBubble("⚠️ Connection error. Please try again.");
    console.error(err);
  }

  setLocked(false);
}

function lockSession() {
  userInput.disabled = true;
  sendBtn.disabled = true;
  userInput.placeholder = "Session ended — click 🔄 New Session to restart";
  subtitle.textContent = "Session ended";
  subtitle.style.color = "var(--wrong)";
}

// ── Event listeners ──────────────────────────────────────────────────────

sendBtn.addEventListener("click", () => {
  const msg = userInput.value.trim();
  if (!msg) return;
  userInput.value = "";
  sendMessage(msg);
});

userInput.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    const msg = userInput.value.trim();
    if (!msg) return;
    userInput.value = "";
    sendMessage(msg);
  }
});

resetBtn.addEventListener("click", async () => {
  await fetch("/reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: SESSION_ID })
  });
  location.reload();
});

// ── XSS safety ──────────────────────────────────────────────────────────

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── Welcome splash on first load ─────────────────────────────────────────

(function showSplash() {
  const splash = document.createElement("div");
  splash.className = "splash";
  splash.innerHTML = `
    <div class="splash-icon">🎓</div>
    <h2>Welcome to the Student Academic Assistant</h2>
    <p>Type <strong>hello</strong> to get started, or <strong>register</strong> to jump straight into the CAT examination.</p>
  `;
  chatWindow.appendChild(splash);
})();
