from __future__ import annotations

from pywinauto import Application


class PywinautoScreenShareAutomation:
    """Discord ekran paylasimi icin UI automation.

    Discord'da ekran paylasimi baslatma/durdurma icin native global hotkey
    yok, bu yuzden pencere otomasyonu kullaniliyor. Discord penceresi acik
    olmali. Discord'un UI'si degisirse (button title/control_type) bu sinif
    guncellenmeli.
    """

    def toggle_share(self, monitor_index: int) -> None:
        app = Application(backend="uia").connect(title_re=".*Discord.*")
        window = app.top_window()
        window.set_focus()

        share_button = window.child_window(
            title="Share Your Screen", control_type="Button"
        )
        share_button.click_input()

        picker_items = window.descendants(control_type="ListItem")
        screen_items = [
            item for item in picker_items if item.window_text().lower().startswith("screen")
        ]
        screen_items[monitor_index].click_input()

        confirm_button = window.child_window(title="Go Live", control_type="Button")
        confirm_button.click_input()
