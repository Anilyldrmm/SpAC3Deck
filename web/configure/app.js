// web/configure/app.js
const TOKEN = new URLSearchParams(window.location.search).get("token");

const CATEGORIES = ["Uygulama & Oyun", "Ses (Voicemeeter)", "Discord", "Medya", "Soundboard", "Makro", "Genel"];

function iconifyUrl(name) {
  return `https://api.iconify.design/lucide/${name}.svg?color=%23d6d6da`;
}

const ACTION_DEFS = {
  steam_launch: { label: "Steam Oyunu", icon: iconifyUrl("gamepad-2"), category: "Uygulama & Oyun", defaultParams: () => ({ appid: "" }) },
  launch_app: { label: "Uygulama Aç", icon: iconifyUrl("rocket"), category: "Uygulama & Oyun", defaultParams: () => ({ path: "" }) },
  open_url: { label: "Web Sitesi Aç", icon: iconifyUrl("globe"), category: "Uygulama & Oyun", defaultParams: () => ({ url: "", browser: "default" }) },
  voicemeeter_mute: { label: "Mikrofon Sustur", icon: iconifyUrl("mic-off"), category: "Ses (Voicemeeter)", defaultParams: () => ({ strip_index: 0 }) },
  voicemeeter_gain: { label: "Giriş Seviyesi", icon: iconifyUrl("volume-2"), category: "Ses (Voicemeeter)", defaultParams: () => ({ strip_index: 0, default_value: 0 }) },
  voicemeeter_route: { label: "Ses Yönlendirme", icon: iconifyUrl("shuffle"), category: "Ses (Voicemeeter)", defaultParams: () => ({ strip_index: 0, bus: "A1" }) },
  voicemeeter_bus_mute: { label: "Çıkış Sustur", icon: iconifyUrl("volume-x"), category: "Ses (Voicemeeter)", defaultParams: () => ({ bus_index: 0 }) },
  voicemeeter_bus_gain: { label: "Çıkış Seviyesi", icon: iconifyUrl("sliders-horizontal"), category: "Ses (Voicemeeter)", defaultParams: () => ({ bus_index: 0, default_value: 0 }) },
  discord_screenshare: { label: "Ekran Paylaş", icon: iconifyUrl("screen-share"), category: "Discord", defaultParams: () => ({ monitor_index: 0 }) },
  discord_stop_share: { label: "Yayını Durdur", icon: iconifyUrl("screen-share-off"), category: "Discord", defaultParams: () => ({}) },
  discord_stream_sound: { label: "Yayın Sesi", icon: iconifyUrl("speaker"), category: "Discord", defaultParams: () => ({}) },
  discord_mic_toggle: { label: "Mikrofon Aç/Kapat", icon: iconifyUrl("mic-off"), category: "Discord", action: "hotkey", defaultParams: () => ({ keys: [] }) },
  discord_deafen_toggle: { label: "Sağırlaştır Aç/Kapat", icon: iconifyUrl("headphone-off"), category: "Discord", action: "hotkey", defaultParams: () => ({ keys: [] }) },
  discord_camera_toggle: { label: "Kamera Aç/Kapat", icon: iconifyUrl("video-off"), category: "Discord", defaultParams: () => ({}) },
  discord_join_channel: { label: "Ses Kanalına Katıl", icon: iconifyUrl("log-in"), category: "Discord", defaultParams: () => ({ guild_id: "", channel_id: "" }) },
  discord_leave_channel: { label: "Bağlantıyı Kes", icon: iconifyUrl("log-out"), category: "Discord", defaultParams: () => ({}) },
  media_play_pause: { label: "Oynat/Duraklat", icon: iconifyUrl("play"), category: "Medya", action: "hotkey", defaultParams: () => ({ keys: ["play/pause media"] }) },
  media_next: { label: "Sonraki Parça", icon: iconifyUrl("skip-forward"), category: "Medya", action: "hotkey", defaultParams: () => ({ keys: ["next track"] }) },
  media_prev: { label: "Önceki Parça", icon: iconifyUrl("skip-back"), category: "Medya", action: "hotkey", defaultParams: () => ({ keys: ["previous track"] }) },
  media_mute: { label: "Sesi Kapat", icon: iconifyUrl("volume-x"), category: "Medya", action: "hotkey", defaultParams: () => ({ keys: ["volume mute"] }) },
  media_volume_up: { label: "Ses Artır", icon: iconifyUrl("volume-2"), category: "Medya", action: "hotkey", defaultParams: () => ({ keys: ["volume up"] }) },
  media_volume_down: { label: "Ses Azalt", icon: iconifyUrl("volume-1"), category: "Medya", action: "hotkey", defaultParams: () => ({ keys: ["volume down"] }) },
  play_sound: { label: "Ses Efekti Çal", icon: iconifyUrl("disc"), category: "Soundboard", defaultParams: () => ({ file: "" }) },
  macro: { label: "Kombinasyon", icon: iconifyUrl("workflow"), category: "Makro", defaultParams: () => ({ steps: [] }) },
  hotkey: { label: "Kısayol Tuşu", icon: iconifyUrl("keyboard"), category: "Genel", defaultParams: () => ({ keys: [] }) },
  hotkey_hold: { label: "Bas-Tut Tuşu", icon: iconifyUrl("timer"), category: "Genel", defaultParams: () => ({ keys: [] }) },
};

const ICON_CHOICES = [
  "star", "flag", "bookmark", "zap", "heart", "circle", "square", "triangle",
  "hexagon", "sparkles", "target", "flame", "snowflake", "sun", "moon",
  "bell", "thumbs-up", "music", "camera", "settings",
].map(iconifyUrl);

const MODIFIER_KEYS = { Control: "ctrl", Shift: "shift", Alt: "alt", Meta: "meta" };

let config = { pages: [] };
let currentPageIndex = 0;
let selectedButtonId = null;
let sources = { voicemeeterStrips: [], voicemeeterBuses: [], monitors: [], steamGames: [], sounds: [] };
let saveTimer = null;

function currentPage() {
  return config.pages[currentPageIndex] || null;
}

function findSelectedButton() {
  const page = currentPage();
  return page ? page.buttons.find((b) => b.id === selectedButtonId) || null : null;
}

// --- loading ---

async function fetchSourceSafe(path) {
  try {
    const response = await fetch(`${path}?token=${encodeURIComponent(TOKEN)}`);
    if (!response.ok) return [];
    return await response.json();
  } catch (e) {
    return [];
  }
}

async function loadSources() {
  const [voicemeeterStrips, voicemeeterBuses, monitors, steamGames, sounds] = await Promise.all([
    fetchSourceSafe("/api/sources/voicemeeter-strips"),
    fetchSourceSafe("/api/sources/voicemeeter-buses"),
    fetchSourceSafe("/api/sources/monitors"),
    fetchSourceSafe("/api/sources/steam-games"),
    fetchSourceSafe("/api/sources/sounds"),
  ]);
  sources = { voicemeeterStrips, voicemeeterBuses, monitors, steamGames, sounds };
}

async function loadConfig() {
  const response = await fetch(`/api/config?token=${encodeURIComponent(TOKEN)}`);
  config = await response.json();
  if (!config.pages.length) config.pages.push({ name: "Genel", buttons: [] });
  if (currentPageIndex >= config.pages.length) currentPageIndex = 0;
  lastSnapshot = snapshotConfig();
  renderTabs();
  renderGrid();
  updateHistoryButtons();
}

// --- saving ---

function setSaveIndicator(state) {
  const el = document.getElementById("save-indicator");
  el.className = state;
  el.textContent = state === "saving" ? "Kaydediliyor…" : state === "error" ? "Kaydedilemedi" : "Kaydedildi";
}

function scheduleSave() {
  if (!isRestoringHistory && !historyPending) {
    pushHistoryCheckpoint();
    historyPending = true;
  }
  setSaveIndicator("saving");
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveConfig, 300);
}

async function saveConfig() {
  try {
    const response = await fetch(`/api/config?token=${encodeURIComponent(TOKEN)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    setSaveIndicator("idle");
    if (!isRestoringHistory) {
      lastSnapshot = snapshotConfig();
      historyPending = false;
    }
  } catch (e) {
    setSaveIndicator("error");
  }
}

// --- undo / redo ---

const MAX_HISTORY = 20;
let undoStack = [];
let redoStack = [];
let lastSnapshot = null;
let historyPending = false;
let isRestoringHistory = false;
let buttonClipboard = null;

function snapshotConfig() {
  return JSON.parse(JSON.stringify(config));
}

function pushHistoryCheckpoint() {
  if (!lastSnapshot) return;
  undoStack.push(lastSnapshot);
  if (undoStack.length > MAX_HISTORY) undoStack.shift();
  redoStack = [];
  updateHistoryButtons();
}

function applyConfigSnapshot(snapshot) {
  isRestoringHistory = true;
  config = JSON.parse(JSON.stringify(snapshot));
  if (!config.pages.length) config.pages.push({ name: "Genel", buttons: [] });
  if (currentPageIndex >= config.pages.length) currentPageIndex = 0;
  closeInspector();
  renderTabs();
  renderGrid();
  scheduleSave();
  lastSnapshot = snapshotConfig();
  isRestoringHistory = false;
}

function undo() {
  if (!undoStack.length) return;
  const previous = undoStack.pop();
  redoStack.push(lastSnapshot);
  applyConfigSnapshot(previous);
  updateHistoryButtons();
}

function redo() {
  if (!redoStack.length) return;
  const next = redoStack.pop();
  undoStack.push(lastSnapshot);
  applyConfigSnapshot(next);
  updateHistoryButtons();
}

function updateHistoryButtons() {
  document.getElementById("undo-btn").disabled = undoStack.length === 0;
  document.getElementById("redo-btn").disabled = redoStack.length === 0;
}

document.getElementById("undo-btn").addEventListener("click", undo);
document.getElementById("redo-btn").addEventListener("click", redo);

document.addEventListener("keydown", (event) => {
  if (!(event.ctrlKey || event.metaKey)) return;
  if (event.key.toLowerCase() !== "z") return;
  const activeTag = document.activeElement ? document.activeElement.tagName : "";
  if (activeTag === "INPUT" || activeTag === "TEXTAREA") return;
  if (document.querySelector(".hotkey-capture.listening")) return;
  event.preventDefault();
  if (event.shiftKey) redo();
  else undo();
});

// --- tabs / pages ---

function renderTabs() {
  const tabsEl = document.getElementById("page-tabs");
  tabsEl.innerHTML = "";
  config.pages.forEach((page, index) => {
    const tab = document.createElement("div");
    tab.className = "page-tab" + (index === currentPageIndex ? " active" : "");
    tab.draggable = true;
    tab.addEventListener("dragstart", (event) => {
      event.dataTransfer.setData("application/x-macrodeck-page-move", String(index));
      event.dataTransfer.effectAllowed = "move";
    });
    tab.addEventListener("dragover", (event) => {
      event.preventDefault();
      tab.classList.add("drag-over");
    });
    tab.addEventListener("dragleave", () => tab.classList.remove("drag-over"));
    tab.addEventListener("drop", (event) => {
      event.preventDefault();
      tab.classList.remove("drag-over");
      const fromRaw = event.dataTransfer.getData("application/x-macrodeck-page-move");
      if (fromRaw === "") return;
      const fromIndex = parseInt(fromRaw, 10);
      if (fromIndex === index) return;
      const [moved] = config.pages.splice(fromIndex, 1);
      const adjustedTarget = fromIndex < index ? index - 1 : index;
      config.pages.splice(adjustedTarget, 0, moved);
      if (currentPageIndex === fromIndex) currentPageIndex = adjustedTarget;
      else if (fromIndex < currentPageIndex && adjustedTarget >= currentPageIndex) currentPageIndex -= 1;
      else if (fromIndex > currentPageIndex && adjustedTarget <= currentPageIndex) currentPageIndex += 1;
      renderTabs();
      renderGrid();
      scheduleSave();
    });

    const nameEl = document.createElement("span");
    nameEl.className = "page-tab-name";
    nameEl.textContent = page.name;
    nameEl.title = "Yeniden adlandırmak için çift tıkla";
    nameEl.addEventListener("click", () => {
      currentPageIndex = index;
      closeInspector();
      renderTabs();
      renderGrid();
    });
    nameEl.addEventListener("dblclick", (event) => {
      event.stopPropagation();
      const input = document.createElement("input");
      input.type = "text";
      input.className = "page-tab-rename";
      input.value = page.name;
      const commit = () => {
        const newName = input.value.trim();
        if (newName) page.name = newName;
        renderTabs();
        scheduleSave();
      };
      input.addEventListener("blur", commit);
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") input.blur();
        if (e.key === "Escape") { input.value = page.name; input.blur(); }
      });
      tab.replaceChild(input, nameEl);
      input.focus();
      input.select();
    });

    tab.appendChild(nameEl);

    if (config.pages.length > 1) {
      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "page-tab-remove";
      removeBtn.textContent = "×";
      removeBtn.title = "Sayfayı sil";
      removeBtn.addEventListener("click", (event) => {
        event.stopPropagation();
        config.pages.splice(index, 1);
        if (currentPageIndex >= config.pages.length) currentPageIndex = config.pages.length - 1;
        closeInspector();
        renderTabs();
        renderGrid();
        scheduleSave();
      });
      tab.appendChild(removeBtn);
    }

    tabsEl.appendChild(tab);
  });
}

document.getElementById("add-page").addEventListener("click", () => {
  config.pages.push({ name: `Sayfa ${config.pages.length + 1}`, buttons: [] });
  currentPageIndex = config.pages.length - 1;
  renderTabs();
  renderGrid();
  scheduleSave();
});

// --- grid ---

function iconSrc(icon) {
  if (icon.startsWith("/api/icon/")) {
    return `${icon}${icon.includes("?") ? "&" : "?"}token=${encodeURIComponent(TOKEN)}`;
  }
  return icon;
}

function renderIconInto(el, icon) {
  el.innerHTML = "";
  if (icon && (icon.startsWith("/api/icon/") || icon.startsWith("http"))) {
    const img = document.createElement("img");
    img.src = iconSrc(icon);
    el.appendChild(img);
  } else {
    el.textContent = icon || "";
  }
}

// Ozel yuklenen gorsel / Steam kapagi: StreamDeck gibi kutunun tamamini kaplasin.
// Lucide cizgi-ikonlar (varsayilanlar) ise kucuk simge olarak kalir.
function isFullBleedIcon(icon) {
  return Boolean(icon) && (icon.startsWith("/api/icon/custom/") || icon.startsWith("/api/icon/steam/"));
}

function renderGrid() {
  const gridEl = document.getElementById("button-grid");
  gridEl.innerHTML = "";
  const page = currentPage();
  if (!page) return;

  page.buttons.forEach((button, index) => {
    gridEl.appendChild(renderCell(button, index));
  });
  gridEl.appendChild(renderEmptyCell(page.buttons.length));
}

function renderCell(button, index) {
  const cell = document.createElement("div");
  cell.className = "grid-cell filled" + (button.id === selectedButtonId ? " selected" : "");
  if (isFullBleedIcon(button.icon)) cell.classList.add("has-image");
  cell.draggable = true;

  const iconEl = document.createElement("div");
  iconEl.className = "icon";
  renderIconInto(iconEl, button.icon);

  const labelEl = document.createElement("div");
  labelEl.className = "label";
  labelEl.textContent = button.label;

  const removeBtn = document.createElement("button");
  removeBtn.className = "remove-btn";
  removeBtn.type = "button";
  removeBtn.textContent = "×";
  removeBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    removeButtonAt(index);
  });

  cell.append(iconEl, labelEl, removeBtn);
  cell.addEventListener("click", () => selectButton(button.id));

  cell.addEventListener("dragstart", (event) => {
    event.dataTransfer.setData("application/x-macrodeck-move", String(index));
    event.dataTransfer.effectAllowed = "move";
  });
  cell.addEventListener("dragover", (event) => {
    event.preventDefault();
    cell.classList.add("drag-over");
  });
  cell.addEventListener("dragleave", () => cell.classList.remove("drag-over"));
  cell.addEventListener("drop", (event) => {
    event.preventDefault();
    cell.classList.remove("drag-over");
    handleDrop(event, index);
  });

  return cell;
}

function renderEmptyCell(insertIndex) {
  const cell = document.createElement("div");
  cell.className = "grid-cell empty";
  cell.textContent = "+";
  if (buttonClipboard) {
    cell.classList.add("has-clipboard");
    cell.title = "Tıkla: kopyalanan butonu yapıştır";
  }
  cell.addEventListener("click", () => {
    if (!buttonClipboard) return;
    const page = currentPage();
    if (!page) return;
    const button = { ...JSON.parse(JSON.stringify(buttonClipboard)), id: `btn-${Date.now()}` };
    page.buttons.splice(insertIndex, 0, button);
    selectButton(button.id);
    renderGrid();
    scheduleSave();
  });
  cell.addEventListener("dragover", (event) => {
    event.preventDefault();
    cell.classList.add("drag-over");
  });
  cell.addEventListener("dragleave", () => cell.classList.remove("drag-over"));
  cell.addEventListener("drop", (event) => {
    event.preventDefault();
    cell.classList.remove("drag-over");
    handleDrop(event, insertIndex);
  });
  return cell;
}

function handleDrop(event, targetIndex) {
  const page = currentPage();
  if (!page) return;

  const actionType = event.dataTransfer.getData("application/x-macrodeck-action");
  if (actionType && ACTION_DEFS[actionType]) {
    const def = ACTION_DEFS[actionType];
    const button = {
      id: `btn-${Date.now()}`,
      label: def.label,
      icon: def.icon,
      action: def.action || actionType,
      params: def.defaultParams(),
    };
    page.buttons.splice(targetIndex, 0, button);
    selectButton(button.id);
    renderGrid();
    scheduleSave();
    return;
  }

  const moveFromRaw = event.dataTransfer.getData("application/x-macrodeck-move");
  if (moveFromRaw !== "") {
    const fromIndex = parseInt(moveFromRaw, 10);
    if (fromIndex === targetIndex) return;
    const [moved] = page.buttons.splice(fromIndex, 1);
    const adjustedTarget = fromIndex < targetIndex ? targetIndex - 1 : targetIndex;
    page.buttons.splice(adjustedTarget, 0, moved);
    renderGrid();
    scheduleSave();
  }
}

function removeButtonAt(index) {
  const page = currentPage();
  if (!page) return;
  const [removed] = page.buttons.splice(index, 1);
  if (removed && removed.id === selectedButtonId) closeInspector();
  renderGrid();
  scheduleSave();
}

// --- action library ---

function renderLibrary(filterText = "") {
  const libEl = document.getElementById("action-library");
  libEl.innerHTML = "";
  const term = filterText.trim().toLowerCase();

  CATEGORIES.forEach((category) => {
    const entries = Object.entries(ACTION_DEFS).filter(
      ([, def]) => def.category === category && (!term || def.label.toLowerCase().includes(term))
    );
    if (!entries.length) return;

    const heading = document.createElement("h3");
    heading.className = "library-category";
    const headingLogo = document.createElement("img");
    headingLogo.className = "library-category-logo";
    headingLogo.src = "/deck/icon-192.png";
    headingLogo.alt = "";
    const headingText = document.createElement("span");
    headingText.textContent = category;
    heading.append(headingLogo, headingText);
    libEl.appendChild(heading);

    entries.forEach(([actionType, def]) => {
      const card = document.createElement("div");
      card.className = "action-card";
      card.draggable = true;

      const iconEl = document.createElement("span");
      iconEl.className = "icon";
      renderIconInto(iconEl, def.icon);
      const labelEl = document.createElement("span");
      labelEl.textContent = def.label;
      card.append(iconEl, labelEl);

      card.addEventListener("dragstart", (event) => {
        event.dataTransfer.setData("application/x-macrodeck-action", actionType);
        event.dataTransfer.effectAllowed = "copy";
        card.classList.add("dragging");
      });
      card.addEventListener("dragend", () => card.classList.remove("dragging"));

      libEl.appendChild(card);
    });
  });
}

// --- inspector ---

function selectButton(buttonId) {
  selectedButtonId = buttonId;
  renderGrid();
  renderInspector();
}

function closeInspector() {
  selectedButtonId = null;
  document.getElementById("inspector").hidden = true;
}

function makeTextField(labelText, value, onChange) {
  const row = document.createElement("div");
  row.className = "field-row";
  const label = document.createElement("label");
  label.textContent = labelText;
  const input = document.createElement("input");
  input.type = "text";
  input.value = value;
  input.addEventListener("input", () => onChange(input.value));
  row.append(label, input);
  return row;
}

function makeSelectField(labelText, options, currentValue, onChange) {
  const row = document.createElement("div");
  row.className = "field-row";
  const label = document.createElement("label");
  label.textContent = labelText;
  const select = document.createElement("select");
  options.forEach((opt) => {
    const optionEl = document.createElement("option");
    optionEl.value = opt.value;
    optionEl.textContent = opt.label;
    optionEl.selected = String(opt.value) === String(currentValue);
    select.appendChild(optionEl);
  });
  select.addEventListener("change", () => onChange(select.value));
  row.append(label, select);
  return row;
}

async function uploadCustomIcon(file) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`/api/icon/upload?token=${encodeURIComponent(TOKEN)}`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const data = await response.json();
  return data.icon;
}

async function uploadSound(file) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`/api/sound/upload?token=${encodeURIComponent(TOKEN)}`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return await response.json();
}

function makeSoundField(params, setParam) {
  const row = document.createElement("div");
  row.className = "field-row";
  const label = document.createElement("label");
  label.textContent = "Ses Dosyası";

  const column = document.createElement("div");

  const select = document.createElement("select");
  const renderOptions = () => {
    select.innerHTML = "";
    const options = [{ file: "", label: "Seç…" }, ...sources.sounds];
    options.forEach((s) => {
      const optionEl = document.createElement("option");
      optionEl.value = s.file;
      optionEl.textContent = s.label;
      optionEl.selected = s.file === (params.file || "");
      select.appendChild(optionEl);
    });
  };
  renderOptions();
  select.addEventListener("change", () => setParam("file", select.value));

  const uploadBtn = document.createElement("button");
  uploadBtn.type = "button";
  uploadBtn.className = "upload-icon-btn";
  uploadBtn.textContent = "🎵 Ses Dosyası Yükle (WAV)";

  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.accept = "audio/wav";
  fileInput.hidden = true;
  fileInput.addEventListener("change", async () => {
    const file = fileInput.files[0];
    if (!file) return;
    try {
      const uploaded = await uploadSound(file);
      sources.sounds.push({ file: uploaded.file, label: uploaded.label });
      setParam("file", uploaded.file);
      renderOptions();
      select.value = uploaded.file;
    } catch (e) {
      uploadBtn.textContent = "Yükleme başarısız, tekrar dene";
    }
  });
  uploadBtn.addEventListener("click", () => fileInput.click());

  column.append(select, uploadBtn, fileInput);
  row.append(label, column);
  return row;
}

const MACRO_STEP_ACTIONS = Object.keys(ACTION_DEFS).filter(
  (key) => !["voicemeeter_gain", "voicemeeter_bus_gain", "hotkey_hold", "macro"].includes(key)
);

function makeMacroField(button, params, setParam) {
  const wrap = document.createElement("div");
  wrap.className = "macro-editor";

  const steps = params.steps || [];

  const renderSteps = () => {
    wrap.innerHTML = "";
    steps.forEach((step, index) => {
      wrap.appendChild(renderMacroStep(step, index));
    });

    const addBtn = document.createElement("button");
    addBtn.type = "button";
    addBtn.className = "upload-icon-btn";
    addBtn.textContent = "+ Adım Ekle";
    addBtn.addEventListener("click", () => {
      const defKey = MACRO_STEP_ACTIONS[0];
      const def = ACTION_DEFS[defKey];
      steps.push({ defKey, action: def.action || defKey, params: def.defaultParams(), delay_ms: 0 });
      setParam("steps", steps);
      renderSteps();
    });
    wrap.appendChild(addBtn);
  };

  function renderMacroStep(step, index) {
    const stepRow = document.createElement("div");
    stepRow.className = "macro-step";

    const header = document.createElement("div");
    header.className = "macro-step-header";

    const actionSelect = document.createElement("select");
    MACRO_STEP_ACTIONS.forEach((defKey) => {
      const optionEl = document.createElement("option");
      optionEl.value = defKey;
      optionEl.textContent = ACTION_DEFS[defKey].label;
      optionEl.selected = defKey === (step.defKey || step.action);
      actionSelect.appendChild(optionEl);
    });
    actionSelect.addEventListener("change", () => {
      const def = ACTION_DEFS[actionSelect.value];
      step.defKey = actionSelect.value;
      step.action = def.action || step.defKey;
      step.params = def.defaultParams();
      setParam("steps", steps);
      renderSteps();
    });

    const delayInput = document.createElement("input");
    delayInput.type = "text";
    delayInput.inputMode = "numeric";
    delayInput.placeholder = "gecikme (ms)";
    delayInput.value = step.delay_ms || 0;
    delayInput.addEventListener("change", () => {
      const parsed = parseInt(delayInput.value, 10);
      step.delay_ms = Number.isFinite(parsed) ? Math.max(0, parsed) : 0;
      setParam("steps", steps);
    });

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "inspector-delete";
    removeBtn.textContent = "Sil";
    removeBtn.addEventListener("click", () => {
      steps.splice(index, 1);
      setParam("steps", steps);
      renderSteps();
    });

    header.append(actionSelect, delayInput, removeBtn);
    stepRow.appendChild(header);

    // adimin kendi params formu (mevcut makeActionParamsFields'i sahte bir buton uzerinden reuse eder)
    const fakeButton = { action: step.action, params: step.params, icon: "", label: "" };
    const stepSetParam = (key, value) => {
      step.params = { ...step.params, [key]: value };
      setParam("steps", steps);
    };
    stepRow.appendChild(makeActionParamsFieldsFor(fakeButton, stepSetParam));

    return stepRow;
  }

  renderSteps();
  return wrap;
}

function makeIconField(button) {
  const row = document.createElement("div");
  row.className = "field-row icon-field-row";
  const label = document.createElement("label");
  label.textContent = "İkon";

  const column = document.createElement("div");

  const grid = document.createElement("div");
  grid.className = "icon-grid";
  ICON_CHOICES.forEach((iconUrl) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = button.icon === iconUrl ? "active" : "";
    const img = document.createElement("img");
    img.src = iconUrl;
    btn.appendChild(img);
    btn.addEventListener("click", () => {
      button.icon = iconUrl;
      renderGrid();
      renderInspector();
      scheduleSave();
    });
    grid.appendChild(btn);
  });

  const uploadBtn = document.createElement("button");
  uploadBtn.type = "button";
  uploadBtn.className = "upload-icon-btn";
  uploadBtn.textContent = "🖼️ Özel Görsel Yükle";

  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.accept = "image/png,image/jpeg,image/webp,image/gif";
  fileInput.hidden = true;
  fileInput.addEventListener("change", async () => {
    const file = fileInput.files[0];
    if (!file) return;
    try {
      button.icon = await uploadCustomIcon(file);
      renderGrid();
      renderInspector();
      scheduleSave();
    } catch (e) {
      uploadBtn.textContent = "Yükleme başarısız, tekrar dene";
    }
  });
  uploadBtn.addEventListener("click", () => fileInput.click());

  column.append(grid, uploadBtn, fileInput);

  const isCustomIcon = button.icon && (button.icon.startsWith("/api/icon/custom/") || button.icon.startsWith("/api/icon/steam/"));
  if (isCustomIcon) {
    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "upload-icon-btn";
    removeBtn.textContent = "🗑️ Özel Görseli Kaldır";
    removeBtn.addEventListener("click", () => {
      button.icon = ACTION_DEFS[button.action]?.icon || ICON_CHOICES[0];
      renderGrid();
      renderInspector();
      scheduleSave();
    });
    column.appendChild(removeBtn);
  }

  row.append(label, column);
  return row;
}

function makeHotkeyField(params, setParam) {
  const row = document.createElement("div");
  row.className = "field-row";
  const label = document.createElement("label");
  label.textContent = "Tuşlar";

  const captureBtn = document.createElement("button");
  captureBtn.type = "button";
  captureBtn.className = "hotkey-capture";
  captureBtn.textContent = (params.keys || []).length ? params.keys.join("+") : "Tıkla, tuşlara bas";

  let listening = false;
  let pressed = [];

  function onKeyDown(event) {
    event.preventDefault();
    const key = MODIFIER_KEYS[event.key] || event.key.toLowerCase();
    if (!pressed.includes(key)) pressed.push(key);
    captureBtn.textContent = pressed.join("+");
  }

  function onKeyUp() {
    if (pressed.length === 0) return;
    setParam("keys", pressed);
    stopListening();
  }

  function stopListening() {
    listening = false;
    captureBtn.classList.remove("listening");
    document.removeEventListener("keydown", onKeyDown);
    document.removeEventListener("keyup", onKeyUp);
  }

  captureBtn.addEventListener("click", () => {
    if (listening) {
      stopListening();
      return;
    }
    listening = true;
    pressed = [];
    captureBtn.classList.add("listening");
    captureBtn.textContent = "Tuşlara bas…";
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("keyup", onKeyUp);
  });

  row.append(label, captureBtn);
  return row;
}

function makeStripField(params, setParam) {
  const options = sources.voicemeeterStrips.length
    ? sources.voicemeeterStrips.map((s) => ({ value: s.index, label: s.label }))
    : [{ value: params.strip_index ?? 0, label: `Strip ${params.strip_index ?? 0}` }];
  return makeSelectField("Voicemeeter Strip", options, params.strip_index ?? 0, (val) =>
    setParam("strip_index", parseInt(val, 10))
  );
}

function makeRouteBusField(params, setParam) {
  const row = document.createElement("div");
  row.className = "field-row";
  const label = document.createElement("label");
  label.textContent = "Hedef Bus";
  const group = document.createElement("div");
  group.className = "bus-group";
  ["A1", "A2", "A3", "B1", "B2", "B3"].forEach((bus) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = bus;
    btn.className = params.bus === bus ? "active" : "";
    btn.addEventListener("click", () => {
      setParam("bus", bus);
      renderInspector();
    });
    group.appendChild(btn);
  });
  row.append(label, group);
  return row;
}

function makeVoicemeeterBusField(params, setParam) {
  const options = sources.voicemeeterBuses.length
    ? sources.voicemeeterBuses.map((b) => ({ value: b.index, label: b.label }))
    : [{ value: params.bus_index ?? 0, label: `Bus ${params.bus_index ?? 0}` }];
  return makeSelectField("Voicemeeter Bus", options, params.bus_index ?? 0, (val) =>
    setParam("bus_index", parseInt(val, 10))
  );
}

function makeDefaultValueField(params, setParam) {
  const row = document.createElement("div");
  row.className = "field-row";
  const label = document.createElement("label");
  label.textContent = "Varsayılan (dB)";
  const input = document.createElement("input");
  input.type = "text";
  input.inputMode = "decimal";
  input.value = params.default_value ?? 0;
  input.addEventListener("change", () => {
    const parsed = parseFloat(input.value);
    setParam("default_value", Number.isFinite(parsed) ? parsed : 0);
  });
  row.append(label, input);
  return row;
}

function makeMonitorField(params, setParam) {
  const options = sources.monitors.length
    ? sources.monitors.map((m) => ({ value: m.index, label: m.label }))
    : [{ value: params.monitor_index ?? 0, label: `Ekran ${(params.monitor_index ?? 0) + 1}` }];
  return makeSelectField("Ekran", options, params.monitor_index ?? 0, (val) =>
    setParam("monitor_index", parseInt(val, 10))
  );
}

function makeSteamField(button, params, setParam) {
  if (!sources.steamGames.length) {
    return makeTextField("Steam AppID", params.appid || "", (val) => setParam("appid", val));
  }
  const options = [{ value: "", label: "Seç…" }, ...sources.steamGames.map((g) => ({ value: g.appid, label: g.name }))];
  return makeSelectField("Steam Oyunu", options, params.appid || "", (val) => {
    setParam("appid", val);
    if (val) {
      button.icon = `/api/icon/steam/${val}`;
      renderGrid();
      renderInspector();
    }
  });
}

function makeActionParamsFields(button) {
  const setParam = (key, value) => {
    button.params = { ...button.params, [key]: value };
    scheduleSave();
  };
  return makeActionParamsFieldsFor(button, setParam);
}

function makeActionParamsFieldsFor(button, setParam) {
  const container = document.createElement("div");
  const params = button.params || {};

  switch (button.action) {
    case "hotkey":
    case "hotkey_hold":
      container.appendChild(makeHotkeyField(params, setParam));
      break;
    case "steam_launch":
      container.appendChild(makeSteamField(button, params, setParam));
      break;
    case "voicemeeter_mute":
      container.appendChild(makeStripField(params, setParam));
      break;
    case "voicemeeter_gain":
      container.appendChild(makeStripField(params, setParam));
      container.appendChild(makeDefaultValueField(params, setParam));
      break;
    case "voicemeeter_route":
      container.appendChild(makeStripField(params, setParam));
      container.appendChild(makeRouteBusField(params, setParam));
      break;
    case "voicemeeter_bus_mute":
      container.appendChild(makeVoicemeeterBusField(params, setParam));
      break;
    case "voicemeeter_bus_gain":
      container.appendChild(makeVoicemeeterBusField(params, setParam));
      container.appendChild(makeDefaultValueField(params, setParam));
      break;
    case "discord_screenshare":
      container.appendChild(makeMonitorField(params, setParam));
      break;
    case "discord_stream_sound":
    case "discord_stop_share":
    case "discord_leave_channel":
    case "discord_camera_toggle":
      break;
    case "discord_join_channel":
      container.appendChild(makeTextField("Sunucu (Guild) ID", params.guild_id || "", (val) => setParam("guild_id", val)));
      container.appendChild(makeTextField("Kanal ID", params.channel_id || "", (val) => setParam("channel_id", val)));
      break;
    case "launch_app":
      container.appendChild(makeTextField("Dosya Yolu", params.path || "", (val) => setParam("path", val)));
      break;
    case "open_url":
      container.appendChild(makeTextField("URL", params.url || "", (val) => setParam("url", val)));
      container.appendChild(
        makeSelectField(
          "Tarayıcı",
          [
            { value: "default", label: "Varsayılan" },
            { value: "chrome", label: "Chrome" },
            { value: "edge", label: "Edge" },
            { value: "firefox", label: "Firefox" },
          ],
          params.browser || "default",
          (val) => setParam("browser", val)
        )
      );
      break;
    case "play_sound":
      container.appendChild(makeSoundField(params, setParam));
      break;
    case "macro":
      container.appendChild(makeMacroField(button, params, setParam));
      break;
  }
  return container;
}

function renderInspector() {
  const button = findSelectedButton();
  const inspectorEl = document.getElementById("inspector");
  if (!button) {
    inspectorEl.hidden = true;
    return;
  }
  inspectorEl.hidden = false;
  inspectorEl.innerHTML = "";

  const title = document.createElement("h3");
  title.textContent = ACTION_DEFS[button.action]?.label || button.action;
  inspectorEl.appendChild(title);

  inspectorEl.appendChild(
    makeTextField("Etiket", button.label, (val) => {
      button.label = val;
      renderGrid();
      scheduleSave();
    })
  );
  inspectorEl.appendChild(makeIconField(button));
  inspectorEl.appendChild(makeActionParamsFields(button));

  const copyBtn = document.createElement("button");
  copyBtn.type = "button";
  copyBtn.className = "inspector-copy";
  copyBtn.textContent = "📋 Kopyala";
  copyBtn.addEventListener("click", () => {
    buttonClipboard = JSON.parse(JSON.stringify(button));
    renderGrid();
  });
  inspectorEl.appendChild(copyBtn);

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "inspector-delete";
  deleteBtn.textContent = "Butonu Sil";
  deleteBtn.addEventListener("click", () => {
    const page = currentPage();
    if (!page) return;
    const idx = page.buttons.findIndex((b) => b.id === button.id);
    if (idx !== -1) removeButtonAt(idx);
  });
  inspectorEl.appendChild(deleteBtn);
}

// --- QR popover ---

function closeOtherPopovers(exceptId) {
  ["qr-popover", "bridge-popover", "history-popover", "settings-popover"].forEach((id) => {
    if (id !== exceptId) document.getElementById(id).hidden = true;
  });
}

document.getElementById("qr-toggle").addEventListener("click", () => {
  const popover = document.getElementById("qr-popover");
  closeOtherPopovers("qr-popover");
  popover.hidden = !popover.hidden;
  if (!popover.hidden) {
    document.getElementById("qr").src = `/api/qr?token=${encodeURIComponent(TOKEN)}`;
  }
});

// --- bridge token popover ---

let bridgeTokenCache = null;

function setBridgeDots(state) {
  // state: "connected" | "disconnected" | null (bilinmiyor)
  [document.getElementById("bridge-dot"), document.getElementById("bridge-status-dot")].forEach((dot) => {
    dot.classList.remove("connected", "disconnected");
    if (state) dot.classList.add(state);
  });
}

async function refreshBridgeStatus() {
  try {
    const response = await fetch(`/api/bridge-token?token=${encodeURIComponent(TOKEN)}`);
    if (!response.ok) throw new Error();
    const data = await response.json();
    bridgeTokenCache = data.bridge_token;
    setBridgeDots(data.bridge_connected ? "connected" : "disconnected");
    return data;
  } catch (e) {
    setBridgeDots(null);
    return null;
  }
}

refreshBridgeStatus();
setInterval(refreshBridgeStatus, 5000);

document.getElementById("bridge-toggle").addEventListener("click", async () => {
  const popover = document.getElementById("bridge-popover");
  closeOtherPopovers("bridge-popover");
  popover.hidden = !popover.hidden;
  if (popover.hidden) return;

  const statusEl = document.getElementById("bridge-status");
  const tokenEl = document.getElementById("bridge-token-display");
  statusEl.textContent = "Yükleniyor…";
  const data = await refreshBridgeStatus();
  if (!data) {
    statusEl.textContent = "Yüklenemedi";
    return;
  }
  statusEl.textContent = data.bridge_connected
    ? "✅ BetterDiscord plugin bağlı"
    : "⚠️ Bağlı değil — plugin ayarlarında token'ı kontrol et";
  tokenEl.textContent = data.bridge_token;
});

// --- history / backup popover ---

function formatBackupTimestamp(unixSeconds) {
  const date = new Date(unixSeconds * 1000);
  return date.toLocaleString("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

async function loadBackupList() {
  const listEl = document.getElementById("backup-list");
  listEl.innerHTML = "";
  const loading = document.createElement("p");
  loading.className = "backup-empty";
  loading.textContent = "Yükleniyor…";
  listEl.appendChild(loading);
  try {
    const response = await fetch(`/api/backups?token=${encodeURIComponent(TOKEN)}`);
    if (!response.ok) throw new Error();
    const backups = await response.json();
    listEl.innerHTML = "";
    if (!backups.length) {
      const empty = document.createElement("p");
      empty.className = "backup-empty";
      empty.textContent = "Henüz kayıtlı sürüm yok.";
      listEl.appendChild(empty);
      return;
    }
    backups.forEach((backup) => {
      const row = document.createElement("div");
      row.className = "backup-item";
      const dateEl = document.createElement("span");
      dateEl.textContent = formatBackupTimestamp(backup.modified);
      const restoreBtn = document.createElement("button");
      restoreBtn.type = "button";
      restoreBtn.textContent = "Bu sürüme dön";
      restoreBtn.addEventListener("click", () => restoreBackupVersion(backup.filename));
      row.append(dateEl, restoreBtn);
      listEl.appendChild(row);
    });
  } catch (e) {
    listEl.innerHTML = "";
    const errEl = document.createElement("p");
    errEl.className = "backup-empty";
    errEl.textContent = "Yüklenemedi";
    listEl.appendChild(errEl);
  }
}

async function restoreBackupVersion(filename) {
  if (!confirm("Bu sürüme dönülsün mü? Mevcut hali de otomatik yedeklenecek.")) return;
  try {
    const response = await fetch(`/api/backups/${encodeURIComponent(filename)}/restore?token=${encodeURIComponent(TOKEN)}`, {
      method: "POST",
    });
    if (!response.ok) throw new Error();
    undoStack = [];
    redoStack = [];
    closeInspector();
    await loadConfig();
    await loadBackupList();
  } catch (e) {
    alert("Geri yükleme başarısız oldu.");
  }
}

document.getElementById("history-toggle").addEventListener("click", async () => {
  const popover = document.getElementById("history-popover");
  closeOtherPopovers("history-popover");
  popover.hidden = !popover.hidden;
  if (popover.hidden) return;
  updateHistoryButtons();
  await loadBackupList();
});

// --- settings popover ---

document.getElementById("settings-toggle").addEventListener("click", async () => {
  const popover = document.getElementById("settings-popover");
  closeOtherPopovers("settings-popover");
  popover.hidden = !popover.hidden;
  if (popover.hidden) return;

  const checkbox = document.getElementById("autostart-checkbox");
  const note = document.getElementById("autostart-note");
  try {
    const response = await fetch(`/api/settings/autostart?token=${encodeURIComponent(TOKEN)}`);
    if (!response.ok) throw new Error();
    const data = await response.json();
    checkbox.checked = data.enabled;
    checkbox.disabled = !data.supported;
    note.textContent = data.supported ? "" : "Bu ayar sadece paketlenmiş (.exe) sürümde kullanılabilir.";
  } catch (e) {
    note.textContent = "Yüklenemedi";
  }

  document.getElementById("grid-columns-input").value = config.grid_columns ?? 5;
  document.getElementById("grid-rows-input").value = config.grid_rows ?? 3;
});

function updateGridSize() {
  const columns = parseInt(document.getElementById("grid-columns-input").value, 10);
  const rows = parseInt(document.getElementById("grid-rows-input").value, 10);
  if (Number.isFinite(columns) && columns >= 1) config.grid_columns = columns;
  if (Number.isFinite(rows) && rows >= 1) config.grid_rows = rows;
  scheduleSave();
}

document.getElementById("grid-columns-input").addEventListener("change", updateGridSize);
document.getElementById("grid-rows-input").addEventListener("change", updateGridSize);

document.getElementById("autostart-checkbox").addEventListener("change", async (event) => {
  const note = document.getElementById("autostart-note");
  try {
    const response = await fetch(`/api/settings/autostart?token=${encodeURIComponent(TOKEN)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: event.target.checked }),
    });
    if (!response.ok) throw new Error();
  } catch (e) {
    event.target.checked = !event.target.checked;
    note.textContent = "Kaydedilemedi";
  }
});

// --- init ---

// --- disari tiklayinca kapat ---

document.addEventListener("click", (event) => {
  const target = event.target;

  ["qr-popover", "bridge-popover", "history-popover", "settings-popover"].forEach((id) => {
    const popover = document.getElementById(id);
    if (popover.hidden) return;
    const toggle = document.getElementById(id.replace("-popover", "-toggle"));
    if (popover.contains(target) || (toggle && toggle.contains(target))) return;
    popover.hidden = true;
  });

  const inspectorEl = document.getElementById("inspector");
  if (!inspectorEl.hidden) {
    const gridEl = document.getElementById("button-grid");
    if (!inspectorEl.contains(target) && !gridEl.contains(target)) {
      closeInspector();
    }
  }
});

document.getElementById("pin-display").textContent = `PIN: ${TOKEN}`;
document.getElementById("library-search").addEventListener("input", (event) => {
  renderLibrary(event.target.value);
});
renderLibrary();
loadConfig();
loadSources();
