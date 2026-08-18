# macrodeck/updater.py
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from . import __version__
from .paths import app_data_dir

logger = logging.getLogger(__name__)

GITHUB_OWNER = "Anilyldrmm"
GITHUB_REPO = "SpAC3Deck"
ASSET_NAME = "MacroDeck-win64.zip"
CHECKSUMS_NAME = "SHA256SUMS.txt"
EXE_NAME = "MacroDeck.exe"

CHECK_INTERVAL_SECONDS = 6 * 60 * 60
STARTUP_DELAY_SECONDS = 10

_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
_REQUEST_TIMEOUT = 15
_DOWNLOAD_CHUNK = 1 << 16
_USER_AGENT = "MacroDeck-Updater"


class UpdateInfo:
    __slots__ = ("version", "download_url", "sha256")

    def __init__(self, version: str, download_url: str, sha256: str):
        self.version = version
        self.download_url = download_url
        self.sha256 = sha256


def _parse_version(tag: str) -> tuple[int, ...]:
    """'v1.2.3' -> (1, 2, 3). Parse edilemeyen parcalar 0 sayilir; tag tamamen
    bossa (0,) doner - boylece bozuk bir tag hicbir zaman "guncel" gibi
    gorunup guncellemeyi engellemez, sadece o dongu atlanir."""
    raw = tag.lstrip("vV")
    parts = []
    for piece in raw.split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) if parts else (0,)


def is_newer(remote_tag: str, current: str = __version__) -> bool:
    return _parse_version(remote_tag) > _parse_version(current)


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})


def _http_get_json(url: str) -> dict:
    with urllib.request.urlopen(_request(url), timeout=_REQUEST_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_get_text(url: str) -> str:
    with urllib.request.urlopen(_request(url), timeout=_REQUEST_TIMEOUT) as resp:
        return resp.read().decode("utf-8")


def _find_asset_url(release: dict, name: str) -> str | None:
    for asset in release.get("assets", []):
        if asset.get("name") == name:
            return asset.get("browser_download_url")
    return None


def _parse_checksums(text: str) -> dict[str, str]:
    """'<hex>  <filename>' formatindaki satirlari {filename: hex} sozlugune cevirir."""
    result: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            result[parts[-1]] = parts[0].lower()
    return result


def check_for_update(current_version: str = __version__) -> UpdateInfo | None:
    """En son GitHub release'ini sorgular; mevcuttan yeniyse UpdateInfo, degilse
    None doner. Ag hatasi, beklenmeyen yanit ya da eksik sha256 -> None (bir
    sonraki periyodik kontrolde sessizce tekrar denenir, kullanici rahatsiz
    edilmez)."""
    try:
        release = _http_get_json(_API_URL)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        logger.info("guncelleme kontrolu basarisiz: %s", exc)
        return None

    tag = release.get("tag_name", "")
    if not tag or not is_newer(tag, current_version):
        return None

    asset_url = _find_asset_url(release, ASSET_NAME)
    if not asset_url:
        logger.warning("release '%s' icinde '%s' asset'i bulunamadi", tag, ASSET_NAME)
        return None

    checksums_url = _find_asset_url(release, CHECKSUMS_NAME)
    sha256 = ""
    if checksums_url:
        try:
            sha256 = _parse_checksums(_http_get_text(checksums_url)).get(ASSET_NAME, "")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.info("checksum dosyasi indirilemedi: %s", exc)

    if not sha256:
        logger.warning("release '%s' icin sha256 bulunamadi, guncelleme atlaniyor", tag)
        return None

    return UpdateInfo(version=tag, download_url=asset_url, sha256=sha256)


def download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(_request(url), timeout=_REQUEST_TIMEOUT) as resp, open(dest, "wb") as out:
        while True:
            chunk = resp.read(_DOWNLOAD_CHUNK)
            if not chunk:
                break
            out.write(chunk)


def verify_sha256(path: Path, expected_hex: str) -> bool:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(_DOWNLOAD_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest().lower() == expected_hex.lower()


def extract_zip(zip_path: Path, dest_dir: Path) -> None:
    """dest_dir onceden varsa temizlenir (yarim kalmis onceki denemeden kalinti
    olabilir). Yayinlanan zip, dist/MacroDeck/ klasorunun ICERIGINI kok
    seviyede barindirmali (klasorun kendisini degil) - extract sonrasi
    dest_dir dogrudan MacroDeck.exe + _internal/ icermeli."""
    if dest_dir.exists():
        shutil.rmtree(dest_dir, ignore_errors=True)
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest_dir)


def install_dir() -> Path:
    """Calisan frozen exe'nin bulundugu klasor - PyInstaller onedir (COLLECT)
    ciktisi, robocopy'nin uzerine yazacagi hedef."""
    return Path(sys.executable).resolve().parent


def staging_dir() -> Path:
    return app_data_dir() / "update_staging"


def build_apply_script(staging: Path, target: Path, exe_name: str, pid: int) -> Path:
    """Cagiran process kapanana kadar bekleyip staging'i target'in uzerine
    kopyalayan ve yeni exe'yi baslatan bir .bat uretir, yolunu doner.

    Ayri bir process olarak calismak zorunda: Windows, calismakta olan bir
    exe'nin kendi dosyalarinin uzerine yazilmasina izin vermez."""
    script_path = app_data_dir() / "apply_update.bat"
    exe_path = target / exe_name
    content = (
        "@echo off\r\n"
        ":wait\r\n"
        f'tasklist /fi "PID eq {pid}" | find "{pid}" >nul\r\n'
        "if not errorlevel 1 (\r\n"
        "  timeout /t 1 /nobreak >nul\r\n"
        "  goto wait\r\n"
        ")\r\n"
        f'robocopy "{staging}" "{target}" /E /IS /IT /R:3 /W:1 >nul\r\n'
        f'start "" "{exe_path}"\r\n'
        f'rmdir /s /q "{staging}"\r\n'
        'del "%~f0"\r\n'
    )
    script_path.write_text(content, encoding="utf-8")
    return script_path


def launch_apply_script(script_path: Path) -> None:
    """CREATE_NO_WINDOW + DETACHED_PROCESS birlikte kullanilmaz: DETACHED_PROCESS
    cmd.exe'ye HICBIR console vermiyor, CREATE_NO_WINDOW ise gizli bir console
    istiyor - bu celiskili kombinasyon script'in icindeki tasklist/timeout/robocopy
    gibi console alt-komutlarinin duzgun calismasini engelleyip bat'i yarim
    birakiyordu (exe hic degismeden, script silinmeden askida kaliyordu - "surekli
    kendi kendini yeniden baslatma" bug'inin sebebi buydu). Sadece CREATE_NO_WINDOW
    yeterli: gorunmez ama gecerli bir console verir, cmd.exe process'ten bagimsiz
    yasamaya devam eder (parent zaten birazdan kapanacak)."""
    subprocess.Popen(
        ["cmd.exe", "/c", str(script_path)],
        creationflags=subprocess.CREATE_NO_WINDOW,
        close_fds=True,
    )


def apply_update(info: UpdateInfo, exe_name: str = EXE_NAME) -> bool:
    """Indir -> sha256 dogrula -> ac -> bekleyen/kopyalayan bat'i baslat.

    True donerse cagiran taraf uygulamayi HEMEN kapatmali (bat, dosyalari
    ancak bu process'in PID'i olunce degistirir). Herhangi bir adim
    basarisiz olursa False doner, mevcut kurulum dokunulmamis kalir ve bir
    sonraki periyodik kontrolde tekrar denenir."""
    staging = staging_dir()
    zip_path = app_data_dir() / "update_download.zip"
    try:
        download_file(info.download_url, zip_path)
        if not verify_sha256(zip_path, info.sha256):
            logger.warning("indirilen guncelleme (%s) sha256 dogrulamasi basarisiz", info.version)
            return False
        extract_zip(zip_path, staging)
    except (urllib.error.URLError, TimeoutError, OSError, zipfile.BadZipFile) as exc:
        logger.info("guncelleme indirme/hazirlama basarisiz: %s", exc)
        return False
    finally:
        zip_path.unlink(missing_ok=True)

    script = build_apply_script(staging, install_dir(), exe_name, os.getpid())
    launch_apply_script(script)
    return True


def run_update_loop(quitting_event, on_apply) -> None:
    """Arka plan thread'inde calisir: baslangictan STARTUP_DELAY_SECONDS sonra
    ve ardindan her CHECK_INTERVAL_SECONDS'ta bir guncelleme kontrol eder.
    Guncelleme bulunup basariyla hazirlanirsa `on_apply()` cagirilir (process'i
    kapatan lifecycle.quit) ve dongu biter - process zaten kapanacagi icin
    tekrar kontrole gerek yok. `quitting_event` set edilirse bekleme
    sirasinda hemen doner, tray'den cikista thread asili kalmaz."""
    if quitting_event.wait(STARTUP_DELAY_SECONDS):
        return
    while not quitting_event.is_set():
        info = check_for_update()
        if info is not None and apply_update(info):
            on_apply()
            return
        if quitting_event.wait(CHECK_INTERVAL_SECONDS):
            return
