"""Paylasilan auth yardimcilari: PIN brute-force limiti ve Origin allowlist.

Hem REST (`/api/*`) hem WebSocket (`/ws`) ayni mantigi kullanir; aksi halde
biri uzerinden brute-force yapip bulunan PIN'i digerinde kullanmak mumkun olur.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Iterable


@dataclass
class _Attempt:
    count: int
    window_start: float
    locked_until: float


class AttemptLimiter:
    """Client IP basina basarisiz PIN denemelerini sayar ve kilitler.

    Davranis: `window` saniyelik pencere icinde `threshold` basarisiz deneme
    olursa IP, son basarisiz denemeden itibaren `lockout` saniye kilitlenir.
    Kilitliyken gelen istekler PIN kontrolune hic girmez ve kilidi uzatmaz.
    Basarili dogrulama sayaci sifirlar.
    """

    def __init__(self, threshold: int = 10, window: float = 60.0, lockout: float = 30.0):
        self.threshold = threshold
        self.window = window
        self.lockout = lockout
        self._entries: dict[str, _Attempt] = {}
        self._lock = threading.Lock()

    def _now(self, now: float | None) -> float:
        return time.monotonic() if now is None else now

    def is_locked(self, client_ip: str, now: float | None = None) -> bool:
        now = self._now(now)
        with self._lock:
            entry = self._entries.get(client_ip)
            if entry is None:
                return False
            if entry.locked_until > now:
                return True
            if entry.locked_until or now - entry.window_start >= self.window:
                # kilit suresi doldu ya da pencere kaydi eskidi
                del self._entries[client_ip]
            return False

    def retry_after(self, client_ip: str, now: float | None = None) -> int:
        """Kilidin bitmesine kalan saniye (kilitli degilse 0)."""
        now = self._now(now)
        with self._lock:
            entry = self._entries.get(client_ip)
            if entry is None or entry.locked_until <= now:
                return 0
            return max(1, int(entry.locked_until - now + 0.999))

    def record_failure(self, client_ip: str, now: float | None = None) -> bool:
        """Basarisiz denemeyi kaydeder; IP bu denemeyle kilitlendiyse True doner."""
        now = self._now(now)
        with self._lock:
            entry = self._entries.get(client_ip)
            if entry is None or now - entry.window_start >= self.window:
                entry = _Attempt(count=0, window_start=now, locked_until=0.0)
                self._entries[client_ip] = entry
            entry.count += 1
            if entry.count >= self.threshold:
                entry.locked_until = now + self.lockout
                return True
            return False

    def reset(self, client_ip: str) -> None:
        with self._lock:
            self._entries.pop(client_ip, None)


def build_allowed_origins(hosts: Iterable[str | None], port: int) -> frozenset[str]:
    """Sunucunun gercekte erisilebildigi origin'lerin listesini uretir."""
    origins: set[str] = set()
    for host in hosts:
        if not host:
            continue
        host = host.strip().lower()
        for scheme, default_port in (("http", 80), ("https", 443)):
            origins.add(f"{scheme}://{host}:{port}")
            if port == default_port:
                origins.add(f"{scheme}://{host}")
    return frozenset(origins)


def normalize_origin(origin: str) -> str:
    return origin.strip().lower().rstrip("/")


def origin_allowed(origin: str | None, allowed: frozenset[str]) -> bool:
    """Origin yoksa (curl, native istemci) izin verilir; varsa allowlist'te olmali.

    Istegin kendi Host header'i ile karsilastirmak DNS rebinding'e aciktir,
    bu yuzden sabit bir allowlist kullaniyoruz.
    """
    if not origin:
        return True
    return normalize_origin(origin) in allowed
