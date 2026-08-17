from __future__ import annotations

import logging
import re
import winreg
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_appmanifest(text: str) -> dict | None:
    """Steam appmanifest_<id>.acf iceriginden {appid, name} cikarir."""
    appid_match = re.search(r'"appid"\s+"(\d+)"', text)
    name_match = re.search(r'"name"\s+"([^"]+)"', text)
    if not appid_match or not name_match:
        return None
    return {"appid": appid_match.group(1), "name": name_match.group(1)}


def parse_library_folders(text: str) -> list[str]:
    """libraryfolders.vdf iceriginden ek Steam kutuphane yollarini cikarir."""
    return re.findall(r'"path"\s+"([^"]+)"', text)


def find_steam_path() -> Path | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            value, _ = winreg.QueryValueEx(key, "SteamPath")
            return Path(value)
    except OSError:
        return None


def _steamapps_dirs(steam_path: Path) -> list[Path]:
    dirs = [steam_path / "steamapps"]
    library_vdf = steam_path / "steamapps" / "libraryfolders.vdf"
    if library_vdf.exists():
        try:
            text = library_vdf.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        for raw_path in parse_library_folders(text):
            dirs.append(Path(raw_path.replace("\\\\", "\\")) / "steamapps")
    return dirs


def list_steam_games() -> list[dict]:
    """Yuklu Steam oyunlarini {appid, name} listesi olarak dondurur, kutuphane bulunamazsa bos liste."""
    steam_path = find_steam_path()
    if steam_path is None:
        return []

    games: list[dict] = []
    seen: set[str] = set()
    for steamapps in _steamapps_dirs(steam_path):
        if not steamapps.is_dir():
            continue
        for manifest in steamapps.glob("appmanifest_*.acf"):
            try:
                text = manifest.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            game = parse_appmanifest(text)
            if game and game["appid"] not in seen:
                seen.add(game["appid"])
                games.append(game)

    return sorted(games, key=lambda g: g["name"].lower())


_BROWSER_EXE_NAMES = {
    "chrome": "chrome.exe",
    "edge": "msedge.exe",
    "firefox": "firefox.exe",
}


def find_browser_path(browser: str) -> str | None:
    """Windows App Paths registry'sinden taraycinin tam exe yolunu bulur."""
    exe_name = _BROWSER_EXE_NAMES.get(browser)
    if exe_name is None:
        return None
    try:
        key_path = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            value, _ = winreg.QueryValueEx(key, "")
            return value
    except OSError:
        return None


def _monitor_label(device: str, rect: tuple[int, int, int, int], is_primary: bool) -> str:
    left, top, right, bottom = rect
    match = re.search(r"(\d+)$", device or "")
    display_number = match.group(1) if match else "?"
    primary_tag = " — Ana Ekran" if is_primary else ""
    return f"Display {display_number} ({right - left}x{bottom - top}){primary_tag}"


def list_monitors() -> list[dict]:
    """Windows'ta bagli ekranlari {index, label} olarak listeler.

    Label'daki numara \\\\.\\DISPLAYn adindan gelir (Windows Ayarlar > Ekran'daki
    numaralarla genelde eslesir). Not: monitor_index (deger) yine de Discord/BD
    plugin'in kendi ekran listesiyle (DiscordNative.desktopCapture) birebir ayni
    sirada olmayabilir - gercek eslesme elle dogrulanmali.
    """
    try:
        import win32api
    except ImportError:
        logger.warning("win32api bulunamadi, ekran listesi alinamiyor")
        return []

    monitors = []
    for index, entry in enumerate(win32api.EnumDisplayMonitors()):
        hmonitor = entry[0]
        info = win32api.GetMonitorInfo(hmonitor)
        device = info.get("Device", "")
        rect = info.get("Monitor", (0, 0, 0, 0))
        is_primary = bool(info.get("Flags", 0) & 1)
        monitors.append({"index": index, "label": _monitor_label(device, rect, is_primary)})
    return monitors
