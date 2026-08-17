from __future__ import annotations

import sys
import winreg

from .paths import is_frozen

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "MacroDeck"


def is_supported() -> bool:
    """Otomatik baslatma sadece paketlenmis (frozen) exe icin anlamli.

    `python -m macrodeck.main` ile gelistirme modunda calisirken Windows'un
    baslangicta calistirabilecegi sabit bir exe yolu yoktur.
    """
    return is_frozen()


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, _VALUE_NAME)
            return True
    except OSError:
        return False


def set_enabled(enabled: bool) -> None:
    if not is_supported():
        return
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, f'"{sys.executable}"')
        else:
            try:
                winreg.DeleteValue(key, _VALUE_NAME)
            except OSError:
                pass
