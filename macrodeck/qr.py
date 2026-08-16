from __future__ import annotations

import io

import qrcode


def generate_deck_url(lan_ip: str, port: int, pin: str) -> str:
    return f"http://{lan_ip}:{port}/deck?token={pin}"


def generate_qr_png(url: str) -> bytes:
    img = qrcode.make(url)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()
