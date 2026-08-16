// web/configure/app.js
const TOKEN = new URLSearchParams(window.location.search).get("token");

let config = { pages: [] };

async function loadConfig() {
  const response = await fetch(`/api/config?token=${TOKEN}`);
  config = await response.json();
  render();
}

async function errorDetail(response) {
  try {
    const body = await response.json();
    if (body && body.detail !== undefined) {
      return typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    }
    return JSON.stringify(body);
  } catch (e) {
    return "";
  }
}

async function saveConfig() {
  let response;
  try {
    response = await fetch(`/api/config?token=${TOKEN}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });
  } catch (e) {
    alert(`Kaydedilemedi: ${e}`);
    return;
  }

  if (!response.ok) {
    const detail = await errorDetail(response);
    alert(`Kaydedilemedi (HTTP ${response.status})${detail ? `: ${detail}` : ""}`);
    return;
  }

  alert("Kaydedildi");
}

function renderQr() {
  const img = document.getElementById("qr");
  if (img) img.src = `/api/qr?token=${encodeURIComponent(TOKEN)}`;
}

function render() {
  const pagesEl = document.getElementById("pages");
  pagesEl.innerHTML = "";
  config.pages.forEach((page, pageIndex) => {
    const pageEl = document.createElement("fieldset");
    const legend = document.createElement("legend");
    legend.textContent = page.name;
    pageEl.appendChild(legend);

    const buttonList = document.createElement("div");
    page.buttons.forEach((button, buttonIndex) => {
      buttonList.appendChild(renderButtonForm(page, button, pageIndex, buttonIndex));
    });
    pageEl.appendChild(buttonList);

    const addButtonBtn = document.createElement("button");
    addButtonBtn.textContent = "+ Buton Ekle";
    addButtonBtn.addEventListener("click", () => {
      page.buttons.push({ id: `btn-${Date.now()}`, label: "Yeni", icon: "🔘", action: "hotkey", params: { keys: [] } });
      render();
    });
    pageEl.appendChild(addButtonBtn);

    pagesEl.appendChild(pageEl);
  });
}

function renderButtonForm(page, button, pageIndex, buttonIndex) {
  const row = document.createElement("div");
  row.className = "button-row";

  const labelInput = document.createElement("input");
  labelInput.value = button.label;
  labelInput.addEventListener("input", () => { button.label = labelInput.value; });

  const actionSelect = document.createElement("select");
  ["hotkey", "hotkey_hold", "steam_launch", "voicemeeter_mute", "voicemeeter_gain", "voicemeeter_route", "discord_screenshare", "launch_app"].forEach((action) => {
    const option = document.createElement("option");
    option.value = action;
    option.textContent = action;
    option.selected = action === button.action;
    actionSelect.appendChild(option);
  });
  actionSelect.addEventListener("change", () => { button.action = actionSelect.value; });

  const paramsInput = document.createElement("input");
  paramsInput.value = JSON.stringify(button.params);
  paramsInput.addEventListener("input", () => {
    try {
      button.params = JSON.parse(paramsInput.value);
    } catch (e) {
      // gecersiz JSON yazilirken bekle, kaydet'te dogrulanir
    }
  });

  const removeBtn = document.createElement("button");
  removeBtn.textContent = "Sil";
  removeBtn.addEventListener("click", () => {
    page.buttons.splice(buttonIndex, 1);
    render();
  });

  row.append(labelInput, actionSelect, paramsInput, removeBtn);
  return row;
}

document.getElementById("add-page").addEventListener("click", () => {
  config.pages.push({ name: `Sayfa ${config.pages.length + 1}`, buttons: [] });
  render();
});

document.getElementById("save").addEventListener("click", saveConfig);

renderQr();
loadConfig();
