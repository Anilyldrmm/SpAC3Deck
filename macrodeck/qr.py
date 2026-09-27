from __future__ import annotations

import io
import re
import socket

import qrcode

_DNS_LABEL = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")


def local_hostname() -> str | None:
    """Bilgisayarin mDNS adini (`<pc-adi>.local`) dondurur.

    DHCP'nin verdigi LAN IP'si zamanla degisiyor ve QR'i gecersiz kiliyor;
    Windows kendi adini mDNS'te yanitladigi icin bu ad sabit kalir. Ad gecerli
    bir DNS etiketi degilse (bosluk, Turkce karakter) None doner.
    """
    name = socket.gethostname().strip().lower()
    if not _DNS_LABEL.match(name):
        return None
    return f"{name}.local"


def generate_deck_url(lan_ip: str, port: int, pin: str) -> str:
    return f"http://{lan_ip}:{port}/deck?token={pin}"


def generate_qr_png(url: str) -> bytes:
    img = qrcode.make(url)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()
