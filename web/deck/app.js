// web/deck/app.js
const PIN_STORAGE_KEY = "macrodeck_pin";
const VOICEMEETER_ACTIONS = ["voicemeeter_mute", "voicemeeter_gain", "voicemeeter_route"];
const VOICEMEETER_BUS_ACTIONS = ["voicemeeter_bus_mute", "voicemeeter_bus_gain"];
const RECONNECT_BASE_MS = 2000;
const RECONNECT_MAX_MS = 8000;
const SLIDER_THROTTLE_MS = 60;

// slider surukleme gibi sik tetiklenen olaylarda gonderimi sinirlar (WS trafigi
// + backend'deki Voicemeeter yazma cagrilarini azaltir)
function throttle(fn, ms) {
  let last = 0;
  let timer = null;
  return (...args) => {
    const now = Date.now();
    const remaining = ms - (now - last);
    if (remaining <= 0) {
      clearTimeout(timer);
      last = now;
      fn(...args);
    } else {
      clearTimeout(timer);
      timer = setTimeout(() => {
        last = Date.now();
        fn(...args);
      }, remaining);
    }
  };
}

const pinGate = document.getElementById("pin-gate");
const pinInput = document.getElementById("pin-input");
const pinSubmit = document.getElementById("pin-submit");
const pinError = document.getElementById("pin-error");
const deckEl = document.getElementById("deck");
const tabsEl = document.getElementById("page-tabs");
const gridEl = document.getElementById("button-grid");
const connBanner = document.getElementById("conn-banner");

let config = null;
let currentPage = 0;
let socket = null;
let currentPin = null;
let lastState = {};
let reconnectAttempts = 0;
let reconnectTimer = null;
// dokunmatikte activeElement guvenilir set olmayabilir (ozellikle iOS'ta range input'lar
// odaklanmayabilir) - poll'un surukleme sirasinda slider'i ezmesini bu set engelliyor
const draggingSliders = new Set();

function safeStorageGet(key) {
  try {
    return localStorage.getItem(key);
  } catch (err) {
    return null;
  }
}

function safeStorageSet(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch (err) {
    // bazi mobil taraycilarda (ozel gezinme, in-app webview) storage engellenmis olabilir;
    // PIN hatirlanmaz ama baglanti bundan dolayi kesilmemeli
  }
}

function getStoredPin() {
  const params = new URLSearchParams(window.location.search);
  return params.get("token") || safeStorageGet(PIN_STORAGE_KEY);
}

function showPinError(message) {
  pinError.textContent = message;
  pinError.hidden = false;
}

function clearPinError() {
  pinError.hidden = true;
}

function showFatalError(message) {
  if (pinGate.hidden) {
    connBanner.hidden = false;
    connBanner.textContent = message;
  } else {
    showPinError(message);
  }
}

window.addEventListener("error", (event) => {
  // sayfaya enjekte olan uzanti/userscript hatalarini yoksay, sadece kendi kodumuzu yakala
  if (event.filename && !event.filename.includes("/deck/app.js")) return;
  showFatalError(`Hata: ${event.message}`);
});
window.addEventListener("unhandledrejection", (event) => {
  showFatalError(`Hata: ${event.reason}`);
});

function applyGridSize() {
  document.documentElement.style.setProperty("--grid-cols", config.grid_columns || 5);
  document.documentElement.style.setProperty("--grid-rows", config.grid_rows || 3);
}

// Grid track'leri "1fr" ile sadece mevcut alani esit bolar, kare garantisi
// vermez. Burada gercek konteyner boyutuna gore olabilecek en buyuk KARE
// hucre boyutu hesaplanip sabit px olarak uygulanir - butonlar hep 1:1 kalir,
// kalan bosluk grid'in kendisi ortalanarak dengelenir (bkz. #button-grid
// justify-content/align-content).
function resizeGridToSquareCells() {
  if (!config) return;
  const cols = config.grid_columns || 5;
  const rows = config.grid_rows || 3;
  const style = getComputedStyle(gridEl);
  const paddingX = parseFloat(style.paddingLeft) + parseFloat(style.paddingRight);
  const paddingY = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
  const colGap = parseFloat(style.columnGap) || 0;
  const rowGap = parseFloat(style.rowGap) || 0;
  const availableWidth = gridEl.clientWidth - paddingX;
  const availableHeight = gridEl.clientHeight - paddingY;
  if (availableWidth <= 0 || availableHeight <= 0) return;

  const cellFromWidth = (availableWidth - (cols - 1) * colGap) / cols;
  const cellFromHeight = (availableHeight - (rows - 1) * rowGap) / rows;
  const cellSize = Math.floor(Math.min(cellFromWidth, cellFromHeight));
  if (cellSize <= 0) return;

  gridEl.style.gridTemplateColumns = `repeat(${cols}, ${cellSize}px)`;
  gridEl.style.gridTemplateRows = `repeat(${rows}, ${cellSize}px)`;
  // buton sayisi grid_rows*grid_cols'u asarsa fazlalar bu "otomatik" satirlara
  // duser - boyut tanimlanmazsa yukseklikleri sifira yakin kalip kayboluyorlardi.
  // ayni kare boyutunu vererek gorunur kalmalarini, #button-grid'in mevcut
  // overflow-y:auto'su sayesinde de asagi kaydirarak ulasilabilir olmalarini
  // sagliyoruz.
  gridEl.style.gridAutoRows = `${cellSize}px`;

  // tasma varsa (buton sayisi grid'i asiyorsa) ustten hizala ki fazlalik hep
  // asagida kalsin ve normal asagi-kaydirma ile ulasilabilsin; tasma yoksa
  // (bosluk varsa) ortala - StreamDeck hissi icin.
  const buttonCount = gridEl.children.length;
  gridEl.style.alignContent = buttonCount > cols * rows ? "start" : "center";
}

const resizeGridThrottled = throttle(resizeGridToSquareCells, 100);
window.addEventListener("resize", resizeGridThrottled);
window.addEventListener("orientationchange", () => setTimeout(resizeGridToSquareCells, 50));

async function connectWithPin(pin) {
  clearPinError();
  if (!pin) {
    showPinError("PIN gir");
    return;
  }

  let response;
  try {
    response = await fetch(`/api/config?token=${encodeURIComponent(pin)}`);
  } catch (err) {
    showPinError("Sunucuya ulaşılamıyor. PC açık ve MacroDeck çalışıyor mu kontrol et.");
    return;
  }

  if (!response.ok) {
    if (response.status === 429) {
      showPinError("Çok fazla deneme, biraz bekle.");
    } else {
      showPinError("PIN yanlış");
    }
    return;
  }

  config = await response.json();
  applyGridSize();
  currentPin = pin;
  safeStorageSet(PIN_STORAGE_KEY, pin);
  pinGate.hidden = true;
  deckEl.hidden = false;
  setConnected(false);
  try {
    renderTabs();
    renderPage(0);
  } catch (err) {
    showFatalError(`Ekran çizilemedi: ${err.message}`);
  }
  openSocket(pin);
}

async function reloadConfig() {
  if (!currentPin) return;
  try {
    const response = await fetch(`/api/config?token=${encodeURIComponent(currentPin)}`);
    if (!response.ok) return;
    config = await response.json();
  } catch (err) {
    return;
  }
  applyGridSize();
  if (currentPage >= config.pages.length) currentPage = 0;
  renderTabs();
  renderPage(currentPage);
}

function renderTabs() {
  tabsEl.innerHTML = "";
  tabsEl.hidden = config.pages.length <= 1;
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

function busIndexOf(button) {
  const params = button.params || {};
  return params.bus_index === undefined || params.bus_index === null ? 0 : params.bus_index;
}

function defaultValueOf(button) {
  const params = button.params || {};
  return params.default_value === undefined || params.default_value === null ? 0 : params.default_value;
}

function flashPressed(el) {
  el.classList.add("pressed");
  setTimeout(() => el.classList.remove("pressed"), 150);
}

// gain slider'i + varsayilana donus butonunu bir satirda birlestirir. dblclick
// dokunmatikte guvenilir tetiklenmiyor, o yuzden ayri bir dokunulabilir buton var.
function buildGainControl(slider, page, button) {
  slider.addEventListener("pointerdown", () => draggingSliders.add(slider));
  const stopDragging = () => draggingSliders.delete(slider);
  slider.addEventListener("pointerup", stopDragging);
  slider.addEventListener("pointercancel", stopDragging);

  const resetBtn = document.createElement("span");
  resetBtn.className = "gain-reset-btn";
  resetBtn.textContent = "↺";
  resetBtn.title = "Varsayılana dön";
  resetBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    const defaultVal = defaultValueOf(button);
    slider.value = String(defaultVal);
    sendEvent(page.name, button.id, "set", defaultVal);
  });

  const row = document.createElement("div");
  row.className = "gain-row";
  row.append(slider, resetBtn);
  return row;
}

function renderPage(index) {
  draggingSliders.clear();
  gridEl.innerHTML = "";
  const page = config.pages[index];
  if (!page) return;
  page.buttons.forEach((button) => {
    const el = document.createElement("button");
    el.className = "deck-button";
    el.dataset.buttonId = button.id;
    el.addEventListener("pointerdown", () => flashPressed(el));

    if (VOICEMEETER_ACTIONS.includes(button.action)) {
      el.dataset.stripIndex = String(stripIndexOf(button));
      el.dataset.kind = button.action === "voicemeeter_mute" ? "mute" : button.action === "voicemeeter_gain" ? "gain-control" : "route";
    } else if (VOICEMEETER_BUS_ACTIONS.includes(button.action)) {
      el.dataset.busIndex = String(busIndexOf(button));
      el.dataset.kind = button.action === "voicemeeter_bus_mute" ? "bus-mute" : "bus-gain-control";
    } else if (button.action === "discord_screenshare") {
      el.dataset.kind = "screenshare";
    } else if (button.action === "discord_stream_sound") {
      el.dataset.kind = "stream-sound";
    } else if (button.action === "discord_camera_toggle") {
      el.dataset.kind = "camera";
    }

    const iconEl = document.createElement("span");
    iconEl.className = "icon";
    if (button.icon && button.icon.startsWith("/api/icon/")) {
      const img = document.createElement("img");
      img.src = `${button.icon}?token=${encodeURIComponent(currentPin)}`;
      iconEl.appendChild(img);
    } else if (button.icon && button.icon.startsWith("http")) {
      const img = document.createElement("img");
      img.src = button.icon;
      iconEl.appendChild(img);
    } else {
      iconEl.textContent = button.icon;
    }
    // ozel yuklenen gorsel / Steam kapagi: butonun tamamini kaplasin (StreamDeck gibi)
    if (button.icon && (button.icon.startsWith("/api/icon/custom/") || button.icon.startsWith("/api/icon/steam/"))) {
      el.classList.add("has-image");
    }

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
      const sendGainThrottled = throttle(
        (value) => sendEvent(page.name, button.id, "set", value),
        SLIDER_THROTTLE_MS
      );
      slider.addEventListener("input", () => {
        sendGainThrottled(parseFloat(slider.value));
      });
      el.appendChild(buildGainControl(slider, page, button));
    } else if (button.action === "voicemeeter_bus_gain") {
      const slider = document.createElement("input");
      slider.type = "range";
      slider.min = "-60";
      slider.max = "12";
      slider.step = "0.5";
      slider.dataset.busIndex = String(busIndexOf(button));
      slider.dataset.kind = "bus-gain";
      const sendBusGainThrottled = throttle(
        (value) => sendEvent(page.name, button.id, "set", value),
        SLIDER_THROTTLE_MS
      );
      slider.addEventListener("input", () => {
        sendBusGainThrottled(parseFloat(slider.value));
      });
      el.appendChild(buildGainControl(slider, page, button));
    } else {
      el.addEventListener("click", () => sendEvent(page.name, button.id, "press"));
    }

    gridEl.appendChild(el);
  });

  resizeGridToSquareCells();

  // yeniden cizimden sonra bilinen son durumu geri uygula
  applyStateDiff(lastState);
}

function sendEvent(pageName, buttonId, event, value) {
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  const payload = { page: pageName, button_id: buttonId, event };
  if (value !== undefined) payload.value = value;
  socket.send(JSON.stringify(payload));
}

function setConnected(connected) {
  connBanner.hidden = connected;
}

function scheduleReconnect() {
  if (reconnectTimer || !currentPin) return;
  const delay = Math.min(RECONNECT_BASE_MS * 2 ** reconnectAttempts, RECONNECT_MAX_MS);
  reconnectAttempts += 1;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    if (currentPin) openSocket(currentPin);
  }, delay);
}

function openSocket(pin) {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  try {
    socket = new WebSocket(`${protocol}://${window.location.host}/ws?token=${encodeURIComponent(pin)}`);
  } catch (err) {
    setConnected(false);
    scheduleReconnect();
    return;
  }

  // bazi mobil taraycilarda handshake hic sonuclanmayabilir (ne open ne error/close
  // gelir); belirli sure sonra hala CONNECTING ise elle basarisiz sayip yeniden dene
  const connectTimeout = setTimeout(() => {
    if (socket && socket.readyState === WebSocket.CONNECTING) {
      socket.close();
    }
  }, 5000);

  socket.addEventListener("open", () => {
    clearTimeout(connectTimeout);
    reconnectAttempts = 0;
    setConnected(true);
  });

  socket.addEventListener("close", () => {
    setConnected(false);
    scheduleReconnect();
  });

  socket.addEventListener("error", () => {
    socket.close();
  });

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
      if (slider && !draggingSliders.has(slider) && document.activeElement !== slider) slider.value = String(value);
      return;
    }

    const busMuteMatch = key.match(/^bus(\d+)_mute$/);
    if (busMuteMatch) {
      const el = document.querySelector(`[data-bus-index="${busMuteMatch[1]}"][data-kind="bus-mute"]`);
      if (el) el.classList.toggle("active", Boolean(value));
      return;
    }

    const busGainMatch = key.match(/^bus(\d+)_gain$/);
    if (busGainMatch) {
      const slider = document.querySelector(`input[data-bus-index="${busGainMatch[1]}"][data-kind="bus-gain"]`);
      if (slider && !draggingSliders.has(slider) && document.activeElement !== slider) slider.value = String(value);
      return;
    }

    if (key === "discord_streaming") {
      document.querySelectorAll('[data-kind="screenshare"]').forEach((el) => el.classList.toggle("active", Boolean(value)));
      // yayin sesi sadece ekran paylasimi acikken anlamli - kapaliyken buton kilitli
      document.querySelectorAll('[data-kind="stream-sound"]').forEach((el) => {
        el.disabled = !value;
      });
      return;
    }

    if (key === "discord_sound") {
      document.querySelectorAll('[data-kind="stream-sound"]').forEach((el) => el.classList.toggle("active", Boolean(value)));
      return;
    }

    if (key === "discord_camera") {
      document.querySelectorAll('[data-kind="camera"]').forEach((el) => el.classList.toggle("active", Boolean(value)));
    }
  });
}

pinSubmit.addEventListener("click", () => connectWithPin(pinInput.value.trim()));
pinInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") connectWithPin(pinInput.value.trim());
});

const storedPin = getStoredPin();
if (storedPin) {
  connectWithPin(storedPin);
}

// sw.js kayitli degil: bos/no-op service worker iOS Safari'de WebSocket
// baglantisinin hic kurulmamasina yol aciyor (bilinen WebKit davranisi).
// Zaten offline cache gibi bir islevi yoktu, kaldirmak guvenli.
