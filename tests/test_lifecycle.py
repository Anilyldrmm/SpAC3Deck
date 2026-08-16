"""Tray + pywebview yasam dongusu (AppLifecycle) davranisi.

Gercek GUI acilmadan test edilebilmesi icin AppLifecycle'a sahte bir webview
modulu enjekte ediliyor.
"""

from types import SimpleNamespace

from macrodeck.main import AppLifecycle


class _FakeEvent:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def fire(self):
        for handler in list(self.handlers):
            handler()


class _FakeWindow:
    def __init__(self, title, url=None, **kwargs):
        self.title = title
        self.url = url
        self.kwargs = kwargs
        self.destroyed = False
        self.shown = 0
        self.events = SimpleNamespace(closed=_FakeEvent())

    def destroy(self):
        self.destroyed = True

    def show(self):
        self.shown += 1

    def close(self):
        """Kullanicinin pencereyi kapatmasini simule eder."""
        self.destroyed = True
        self.events.closed.fire()


class _FakeWebview:
    def __init__(self):
        self.windows = []
        self.start_calls = 0

    def create_window(self, title, url=None, **kwargs):
        window = _FakeWindow(title, url, **kwargs)
        self.windows.append(window)
        return window

    def start(self, *args, **kwargs):
        self.start_calls += 1


class _FakeIcon:
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True


class _FakeBackend:
    def __init__(self):
        self.logged_out = False

    def logout(self):
        self.logged_out = True


def _build(webview_module=None, backend=None):
    fake_webview = webview_module or _FakeWebview()
    app = SimpleNamespace(state=SimpleNamespace(
        voicemeeter_backend=backend,
        voicemeeter_client=object() if backend else None,
    ))
    lifecycle = AppLifecycle(
        app,
        "http://localhost:8765/configure?token=1234",
        webview_module=fake_webview,
        exit_grace=None,  # testte os._exit watchdog'u kapali
    )
    return lifecycle, fake_webview, app


def test_open_configurator_never_starts_a_second_gui_loop():
    """Tray callback'i sadece pencere olusturur; webview.start cagirmaz."""
    lifecycle, fake_webview, _ = _build()
    lifecycle.open_configurator()
    lifecycle.open_configurator()
    assert fake_webview.start_calls == 0


def test_open_configurator_does_not_create_duplicate_windows():
    lifecycle, fake_webview, _ = _build()
    first = lifecycle.open_configurator()
    second = lifecycle.open_configurator()

    assert first is second
    assert len(fake_webview.windows) == 1
    assert first.shown == 1  # ikinci cagri mevcut pencereyi one getirir


def test_configurator_can_be_reopened_after_close():
    lifecycle, fake_webview, _ = _build()
    first = lifecycle.open_configurator()
    first.close()  # kullanici pencereyi kapatti

    second = lifecycle.open_configurator()
    assert second is not first
    assert len(fake_webview.windows) == 2


def test_keepalive_window_is_hidden():
    """Gizli keep-alive penceresi GUI dongusunu (ve process'i) ayakta tutar."""
    lifecycle, fake_webview, _ = _build()
    window = lifecycle.create_keepalive_window()
    assert window.kwargs.get("hidden") is True
    assert fake_webview.windows == [window]


def test_quit_stops_tray_logs_out_voicemeeter_and_destroys_windows():
    backend = _FakeBackend()
    lifecycle, fake_webview, app = _build(backend=backend)
    keepalive = lifecycle.create_keepalive_window()
    configurator = lifecycle.open_configurator()

    icon = _FakeIcon()
    lifecycle.quit(icon)

    assert icon.stopped is True
    assert backend.logged_out is True
    assert keepalive.destroyed is True
    assert configurator.destroyed is True
    assert lifecycle.is_quitting is True
    assert app.state.voicemeeter_client is None


def test_quit_is_idempotent_and_blocks_reopening():
    backend = _FakeBackend()
    lifecycle, fake_webview, _ = _build(backend=backend)
    icon = _FakeIcon()

    lifecycle.quit(icon)
    lifecycle.quit(icon)  # ikinci cagri no-op olmali

    assert lifecycle.open_configurator() is None
    assert fake_webview.windows == []


def test_quit_without_voicemeeter_does_not_raise():
    lifecycle, _, _ = _build(backend=None)
    lifecycle.quit(_FakeIcon())
    assert lifecycle.is_quitting is True


def test_quit_schedules_force_exit_watchdog():
    """Temiz cikis takilirsa process yine de kapanmali."""
    calls = []
    fake_webview = _FakeWebview()
    app = SimpleNamespace(state=SimpleNamespace(voicemeeter_backend=None, voicemeeter_client=None))
    lifecycle = AppLifecycle(
        app,
        "http://localhost:8765/configure?token=1234",
        webview_module=fake_webview,
        exit_grace=0.01,
        force_exit=lambda code: calls.append(code),
    )
    lifecycle.quit(_FakeIcon())

    deadline = __import__("time").monotonic() + 2.0
    while not calls and __import__("time").monotonic() < deadline:
        __import__("time").sleep(0.01)
    assert calls == [0]
