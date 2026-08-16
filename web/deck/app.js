// web/deck/app.js
const PIN_STORAGE_KEY = "macrodeck_pin";

const pinGate = document.getElementById("pin-gate");
const pinInput = document.getElementById("pin-input");
const pinSubmit = document.getElementById("pin-submit");
const deckEl = document.getElementById("deck");
const tabsEl = document.getElementById("page-tabs");
const gridEl = document.getElementById("button-grid");

let config = null;
let currentPage = 0;
let socket = null;

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
  localStorage.setItem(PIN_STORAGE_KEY, pin);
  pinGate.hidden = true;
  deckEl.hidden = false;
  renderTabs();
  renderPage(0);
  openSocket(pin);
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

function renderPage(index) {
  gridEl.innerHTML = "";
  const page = config.pages[index];
  page.buttons.forEach((button) => {
    const el = document.createElement("button");
    el.className = "deck-button";
    el.dataset.buttonId = button.id;

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
      slider.addEventListener("input", () => {
        sendEvent(page.name, button.id, "set", parseFloat(slider.value));
      });
      el.appendChild(slider);
    } else {
      el.addEventListener("click", () => sendEvent(page.name, button.id, "press"));
    }

    gridEl.appendChild(el);
  });
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
      applyStateDiff(message.data);
    }
  });
}

function applyStateDiff(diff) {
  Object.entries(diff).forEach(([key, value]) => {
    const match = key.match(/^strip(\d+)_mute$/);
    if (match) {
      const stripIndex = match[1];
      const el = document.querySelector(`[data-strip-index="${stripIndex}"][data-kind="mute"]`);
      if (el) el.classList.toggle("active", Boolean(value));
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
