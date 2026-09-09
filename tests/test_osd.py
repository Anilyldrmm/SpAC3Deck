"""Ekran ustu ses gostergesi: konum cozumleme ve gorunurluk durum makinesi.

Gercek tkinter penceresi acilmaz; VolumeOsd'ye fake bir cizim yuzeyi ve
sahte saat enjekte edilir, dongu adimlari elle (`tick`) surulur.
"""
from macrodeck.config import DeckConfig, MediaKeysConfig
from macrodeck.osd import (
    CARD_HEIGHT,
    CARD_WIDTH,
    HIDE_AFTER_SECONDS,
    PLACEMENT_TIMEOUT_SECONDS,
    SCREEN_MARGIN,
    VolumeOsd,
    default_position,
    format_gain,
    gain_fraction,
    interactive_ex_style,
    passive_ex_style,
    resolve_position,
)

_WS_EX_TRANSPARENT = 0x00000020
_WS_EX_TOOLWINDOW = 0x00000080
_WS_EX_NOACTIVATE = 0x08000000
_WS_EX_LAYERED = 0x00080000

PRIMARY = {"rect": (0, 0, 1920, 1080), "primary": True}
SECONDARY_LEFT = {"rect": (-1920, 0, 0, 1080), "primary": False}


class FakeSurface:
    def __init__(self, on_drag_end=None):
        self.on_drag_end = on_drag_end
        self.frames = []
        self.moves = []
        self.visible = False
        self.interactive = None
        self.pumps = 0
        self.destroyed = False

    def render(self, frame):
        self.frames.append(frame)

    def move(self, x, y):
        self.moves.append((x, y))

    def set_visible(self, visible):
        self.visible = visible

    def set_interactive(self, interactive):
        self.interactive = interactive

    def pump(self):
        self.pumps += 1

    def destroy(self):
        self.destroyed = True

    def drag_to(self, x, y):
        self.on_drag_end(x, y)


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def make_osd(config=None, monitors=None):
    config = config or DeckConfig(media_keys=MediaKeysConfig(enabled=True, osd_enabled=True))
    surfaces = []

    def factory(on_drag_end):
        surface = FakeSurface(on_drag_end)
        surfaces.append(surface)
        return surface

    clock = FakeClock()
    osd = VolumeOsd(
        get_config=lambda: config,
        surface_factory=factory,
        monitor_lister=lambda: monitors if monitors is not None else [PRIMARY],
        clock=clock,
    )
    osd.open()
    return osd, surfaces[0], clock, config


# --- saf yardimcilar ---

def test_gain_fraction_clamps_to_unit_range():
    assert gain_fraction(-90.0) == 0.0
    assert gain_fraction(60.0) == 1.0
    assert 0.0 < gain_fraction(-12.0) < 1.0


def test_format_gain_always_shows_sign():
    assert format_gain(-6.0) == "-6.0 dB"
    assert format_gain(0.0) == "+0.0 dB"
    assert format_gain(3.5) == "+3.5 dB"


def test_default_position_is_bottom_center_of_primary_monitor():
    x, y = default_position([SECONDARY_LEFT, PRIMARY])

    assert x == (1920 - CARD_WIDTH) // 2
    assert y == 1080 - CARD_HEIGHT - SCREEN_MARGIN


def test_default_position_without_monitors_falls_back_to_origin():
    assert default_position([]) == (0, 0)


def test_resolve_position_keeps_coordinate_on_secondary_monitor():
    """Yan monitorde x negatif olabilir - mutlak sanal ekran koordinati korunmali."""
    assert resolve_position(-1500, 800, [PRIMARY, SECONDARY_LEFT]) == (-1500, 800)


def test_resolve_position_falls_back_when_saved_coordinate_is_offscreen():
    """Monitor cikarilinca kart gorunmez bir yerde kalmasin."""
    assert resolve_position(-1500, 800, [PRIMARY]) == default_position([PRIMARY])


def test_resolve_position_falls_back_when_unset():
    assert resolve_position(None, None, [PRIMARY]) == default_position([PRIMARY])


# --- gorunurluk durum makinesi ---

def test_show_renders_and_makes_card_visible():
    osd, surface, _clock, _config = make_osd()

    osd.show("Strip 0", -6.0, muted=False)
    osd.tick()

    assert surface.visible is True
    assert len(surface.frames) == 1
    frame = surface.frames[0]
    assert frame.label == "Strip 0"
    assert frame.gain_db == -6.0
    assert frame.muted is False
    assert frame.fraction == gain_fraction(-6.0)


def test_show_positions_card_from_config_coordinates():
    config = DeckConfig(media_keys=MediaKeysConfig(
        enabled=True, osd_enabled=True, osd_x=-1500, osd_y=800,
    ))
    osd, surface, _clock, _config = make_osd(config, monitors=[PRIMARY, SECONDARY_LEFT])

    osd.show("Strip 0", -6.0, muted=False)
    osd.tick()

    assert surface.moves[-1] == (-1500, 800)


def test_show_is_ignored_when_osd_disabled_in_config():
    config = DeckConfig(media_keys=MediaKeysConfig(enabled=True, osd_enabled=False))
    osd, surface, _clock, _config = make_osd(config)

    osd.show("Strip 0", -6.0, muted=False)
    osd.tick()

    assert surface.frames == []
    assert surface.visible is False


def test_card_hides_itself_after_timeout():
    osd, surface, clock, _config = make_osd()
    osd.show("Strip 0", -6.0, muted=False)
    osd.tick()

    clock.advance(HIDE_AFTER_SECONDS + 0.1)
    osd.tick()

    assert surface.visible is False


def test_new_show_resets_the_hide_timer():
    osd, surface, clock, _config = make_osd()
    osd.show("Strip 0", -6.0, muted=False)
    osd.tick()

    clock.advance(HIDE_AFTER_SECONDS - 0.1)
    osd.show("Strip 0", -3.0, muted=False)
    osd.tick()
    clock.advance(HIDE_AFTER_SECONDS - 0.1)
    osd.tick()

    assert surface.visible is True


def test_muted_show_passes_mute_flag_through():
    osd, surface, _clock, _config = make_osd()

    osd.show("Bus 1", -12.0, muted=True)
    osd.tick()

    assert surface.frames[-1].muted is True


# --- yerlestirme modu ---

def test_placement_mode_keeps_card_visible_and_interactive():
    osd, surface, clock, _config = make_osd()

    osd.set_placement(True)
    osd.tick()
    clock.advance(HIDE_AFTER_SECONDS * 3)
    osd.tick()

    assert surface.visible is True
    assert surface.interactive is True
    assert surface.frames[-1].placement is True


def test_leaving_placement_mode_hides_card_and_restores_passive_styles():
    osd, surface, _clock, _config = make_osd()
    osd.set_placement(True)
    osd.tick()

    osd.set_placement(False)
    osd.tick()

    assert surface.visible is False
    assert surface.interactive is False


def test_drag_updates_position_and_is_returned_when_placement_ends():
    osd, surface, _clock, _config = make_osd(monitors=[PRIMARY, SECONDARY_LEFT])
    osd.set_placement(True)
    osd.tick()

    surface.drag_to(-1200, 300)
    position = osd.set_placement(False)

    assert position == (-1200, 300)
    assert osd.position == (-1200, 300)


def test_dragged_position_survives_ticks_while_still_in_placement_mode():
    """Surukleme sonrasi tick, config'deki eski konumu geri yazmamali."""
    osd, surface, _clock, _config = make_osd()
    osd.set_placement(True)
    osd.tick()

    surface.drag_to(640, 200)
    osd.show("Strip 0", -6.0, muted=False)
    osd.tick()

    assert osd.position == (640, 200)


def test_close_destroys_the_surface():
    osd, surface, _clock, _config = make_osd()

    osd.close()

    assert surface.destroyed is True


# --- ex-style bit matematigi (odak calmama garantisinin kalbi) ---

def test_passive_ex_style_sets_all_three_protection_bits():
    updated = passive_ex_style(_WS_EX_LAYERED)

    assert updated & _WS_EX_NOACTIVATE
    assert updated & _WS_EX_TOOLWINDOW
    assert updated & _WS_EX_TRANSPARENT
    assert updated & _WS_EX_LAYERED  # tk'nin -alpha icin actigi bit bozulmamali


def test_interactive_ex_style_drops_noactivate_and_transparent_but_keeps_toolwindow():
    """Yerlestirme modunda kart fare olayi almali ama alt-tab'da gorunmemeli."""
    updated = interactive_ex_style(passive_ex_style(_WS_EX_LAYERED))

    assert not updated & _WS_EX_NOACTIVATE
    assert not updated & _WS_EX_TRANSPARENT
    assert updated & _WS_EX_TOOLWINDOW
    assert updated & _WS_EX_LAYERED


# --- yerlestirme modunun dayanikliligi ---

def test_dragged_position_is_not_overwritten_when_placement_ends():
    """Regresyon: mod kapanirken config'deki eski konum sürüklenen konumu ezmemeli."""
    config = DeckConfig(media_keys=MediaKeysConfig(
        enabled=True, osd_enabled=True, osd_x=100, osd_y=100,
    ))
    osd, surface, _clock, _config = make_osd(config)
    osd.set_placement(True)
    osd.tick()

    surface.drag_to(500, 500)
    returned = osd.set_placement(False)
    osd.tick()

    assert returned == (500, 500)
    assert osd.position == (500, 500)


def test_placement_is_refused_while_osd_disabled():
    config = DeckConfig(media_keys=MediaKeysConfig(enabled=True, osd_enabled=False))
    osd, surface, _clock, _config = make_osd(config)

    osd.set_placement(True)
    osd.tick()

    assert surface.visible is False
    assert surface.frames == []


def test_placement_times_out_so_the_card_cannot_stay_interactive_forever():
    """Configurator yerlestirme modunda kapatilirsa kart ekranda takili kalmasin."""
    osd, surface, clock, _config = make_osd()
    osd.set_placement(True)
    osd.tick()

    clock.advance(PLACEMENT_TIMEOUT_SECONDS + 1)
    osd.tick()

    assert surface.visible is False
    assert surface.interactive is False


def test_set_placement_returns_config_position_when_nothing_dragged_yet():
    config = DeckConfig(media_keys=MediaKeysConfig(
        enabled=True, osd_enabled=True, osd_x=-1500, osd_y=800,
    ))
    osd, _surface, _clock, _config = make_osd(config, monitors=[PRIMARY, SECONDARY_LEFT])

    assert osd.set_placement(True) == (-1500, 800)


def test_volume_event_during_placement_keeps_the_drag_hint_on_screen():
    osd, surface, _clock, _config = make_osd()
    osd.set_placement(True)
    osd.tick()

    osd.show("Strip 0", -6.0, muted=False)
    osd.tick()

    assert surface.frames[-1].placement is True


# --- dongu dayanikliligi ---

class ExplodingSurface(FakeSurface):
    def __init__(self, on_drag_end=None):
        super().__init__(on_drag_end)
        self.explode = True

    def render(self, frame):
        if self.explode:
            raise RuntimeError("tk hata verdi")
        super().render(frame)


def test_single_tick_error_does_not_kill_the_osd_thread():
    """Gecici bir Tk hatasi gostergeyi oturum sonuna kadar oldurmemeli."""
    config = DeckConfig(media_keys=MediaKeysConfig(enabled=True, osd_enabled=True))
    surfaces = []

    def factory(on_drag_end):
        surface = ExplodingSurface(on_drag_end)
        surfaces.append(surface)
        return surface

    osd = VolumeOsd(
        get_config=lambda: config,
        surface_factory=factory,
        monitor_lister=lambda: [PRIMARY],
        clock=FakeClock(),
    )
    osd.open()
    surface = surfaces[0]

    osd.show("Strip 0", -6.0, muted=False)
    try:
        osd.tick()
    except RuntimeError:
        pass  # _run bu istisnayi yakalar, tick disariya birakir

    surface.explode = False
    osd.show("Strip 0", -3.0, muted=False)
    osd.tick()

    assert surface.visible is True
    assert surface.frames[-1].gain_db == -3.0


def test_queue_is_bounded_so_a_dead_osd_thread_cannot_leak_memory():
    osd, _surface, _clock, _config = make_osd()

    for _ in range(500):
        osd.show("Strip 0", -6.0, muted=False)

    assert osd._queue.qsize() <= 32


def test_is_running_is_false_before_start_and_after_stop():
    osd, _surface, _clock, _config = make_osd()

    assert osd.is_running() is False  # thread hic baslatilmadi

    osd.stop()

    assert osd.is_running() is False
