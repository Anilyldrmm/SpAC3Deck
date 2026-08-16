# macrodeck/main.py
from __future__ import annotations

import socket
import threading
from pathlib import Path

import uvicorn
import webview

from .server import create_app, configure_runtime
from .tray import start_tray

PORT = 8765
CONFIG_PATH = Path("config/deck.json")


def _get_lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


def _run_server(app):
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")


def main() -> None:
    app = create_app(config_path=CONFIG_PATH)
    configure_runtime(app, voicemeeter_kind="banana")

    server_thread = threading.Thread(target=_run_server, args=(app,), daemon=True)
    server_thread.start()

    lan_ip = _get_lan_ip()
    print(f"Deck URL: http://{lan_ip}:{PORT}/deck?token={app.state.pin}")
    print(f"Configurator URL: http://localhost:{PORT}/configure?token={app.state.pin}")

    def open_configurator():
        webview.create_window(
            "MacroDeck Configurator",
            f"http://localhost:{PORT}/configure?token={app.state.pin}",
        )
        webview.start()

    def quit_app(icon):
        icon.stop()

    start_tray(open_configurator, quit_app)
    open_configurator()


if __name__ == "__main__":
    main()
