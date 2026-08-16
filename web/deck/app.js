// web/deck/app.js
const PIN_STORAGE_KEY = "macrodeck_pin";
const VOICEMEETER_ACTIONS = ["voicemeeter_mute", "voicemeeter_gain", "voicemeeter_route"];

const pinGate = document.getElementById("pin-gate");
const pinInput = document.getElementById("pin-input");
const pinSubmit = document.getElementById("pin-submit");
const deckEl = document.getElementById("deck");
const tabsEl = document.getElementById("page-tabs");
const gridEl = document.getElementById("button-grid");

let config = null;
let currentPage = 0;
let socket = null;
let currentPin = null;
let lastState = {};

function getStoredPin() {
  const params = new URLSearchParams(window.location.search);
  return params.get("token") || localStorage.getItem(PIN_STORAGE_KEY);
}

async function connectWithPin(pin) {
  const response = await fetch(`/api/config?token=${encodeURIComponent(pin)}`);
  if (!response.ok) {
    alert("PIN yanlış");
    return;
  }
  config = await response.json();
  currentPin = pin;
  localStorage.setItem(PIN_STORAGE_KEY, pin);
  pinGate.hidden = true;
  deckEl.hidden = false;
  renderTabs();
  renderPage(0);
  openSocket(pin);
}

async function reloadConfig() {
  if (!currentPin) return;
  const response = await fetch(`/api/config?token=${encodeURIComponent(currentPin)}`);
  if (!response.ok) return;
  config = await response.json();
  if (currentPage >= config.pages.length) currentPage = 0;
  renderTabs();
  renderPage(currentPage);
}

function renderTabs() {
  tabsEl.innerHTML = "";
  config.pages.forEach((page, index) => {
    const tab = document.createElement("button");
    tab.textContent = page.name;
    tab.className = index === currentPage ? "active" : "";
    tab.addEventListener("click", () => {
      currentPage = index;
      renderTabs();
      renderPage(index);
    });
    tabsEl.appendChild(tab);
  });
}

function stripIndexOf(button) {
  const params = button.params || {};
  return params.strip_index === undefined || params.strip_index === null ? 0 : params.strip_index;
}

function renderPage(index) {
  gridEl.innerHTML = "";
  const page = config.pages[index];
  if (!page) return;
  page.buttons.forEach((button) => {
    const el = document.createElement("button");
    el.className = "deck-button";
    el.dataset.buttonId = button.id;

    if (VOICEMEETER_ACTIONS.includes(button.action)) {
      el.dataset.stripIndex = String(stripIndexOf(button));
      el.dataset.kind = button.action === "voicemeeter_mute" ? "mute" : button.action === "voicemeeter_gain" ? "gain-control" : "route";
    }

    const iconEl = document.createElement("span");
    iconEl.className = "icon";
    iconEl.textContent = button.icon;

    const labelEl = document.createElement("span");
    labelEl.className = "label";
    labelEl.textContent = button.label;

    el.append(iconEl, labelEl);

    if (button.action === "hotkey_hold") {
      el.addEventListener("touchstart", () => sendEvent(page.name, button.id, "press"));
      el.addEventListener("touchend", () => sendEvent(page.name, button.id, "release"));
      el.addEventListener("mousedown", () => sendEvent(page.name, button.id, "press"));
      el.addEventListener("mouseup", () => sendEvent(page.name, button.id, "release"));
    } else if (button.action === "voicemeeter_gain") {
      const slider = document.createElement("input");
      slider.type = "range";
      slider.min = "-60";
      slider.max = "12";
      slider.step = "0.5";
      // state broadcast'i slider'i bulabilsin diye
      slider.dataset.stripIndex = String(stripIndexOf(button));
      slider.dataset.kind = "gain";
      slider.addEventListener("input", () => {
        sendEvent(page.name, button.id, "set", parseFloat(slider.value));
      });
      el.appendChild(slider);
    } else {
      el.addEventListener("click", () => sendEvent(page.name, button.id, "press"));
    }

    gridEl.appendChild(el);
  });

  // yeniden cizimden sonra bilinen son durumu geri uygula
  applyStateDiff(lastState);
}

function sendEvent(pageName, buttonId, event, value) {
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  const payload = { page: pageName, button_id: buttonId, event };
  if (value !== undefined) payload.value = value;
  socket.send(JSON.stringify(payload));
}

function openSocket(pin) {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${protocol}://${window.location.host}/ws?token=${encodeURIComponent(pin)}`);
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "state") {
      Object.assign(lastState, message.data);
      applyStateDiff(message.data);
    } else if (message.type === "reload") {
      reloadConfig();
    }
  });
}

function applyStateDiff(diff) {
  Object.entries(diff).forEach(([key, value]) => {
    const muteMatch = key.match(/^strip(\d+)_mute$/);
    if (muteMatch) {
      const el = document.querySelector(`[data-strip-index="${muteMatch[1]}"][data-kind="mute"]`);
      if (el) el.classList.toggle("active", Boolean(value));
      return;
    }

    const gainMatch = key.match(/^strip(\d+)_gain$/);
    if (gainMatch) {
      const slider = document.querySelector(`input[data-strip-index="${gainMatch[1]}"][data-kind="gain"]`);
      // kullanici o an slider'i tutuyorsa degerini ezme
      if (slider && document.activeElement !== slider) slider.value = String(value);
    }
  });
}

pinSubmit.addEventListener("click", () => connectWithPin(pinInput.value.trim()));

const storedPin = getStoredPin();
if (storedPin) {
  connectWithPin(storedPin);
}

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js");
}
