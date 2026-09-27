from macrodeck.sources import parse_appmanifest, parse_library_folders, _monitor_label, find_browser_path, pick_cached_steam_image


def test_parse_appmanifest_extracts_appid_and_name():
    text = """
    "AppState"
    {
        "appid"		"730"
        "Universe"		"1"
        "name"		"Counter-Strike 2"
    }
    """
    assert parse_appmanifest(text) == {"appid": "730", "name": "Counter-Strike 2"}


def test_parse_appmanifest_returns_none_when_fields_missing():
    assert parse_appmanifest('"AppState"\n{\n"Universe" "1"\n}') is None


def test_parse_library_folders_extracts_paths():
    text = """
    "libraryfolders"
    {
        "0"
        {
            "path"		"C:\\\\SteamLibrary"
        }
        "1"
        {
            "path"		"D:\\\\Games\\\\Steam"
        }
    }
    """
    assert parse_library_folders(text) == ["C:\\\\SteamLibrary", "D:\\\\Games\\\\Steam"]


def test_monitor_label_includes_resolution_and_display_number():
    label = _monitor_label("\\\\.\\DISPLAY1", (0, 0, 1920, 1080), False)
    assert label == "Display 1 (1920x1080)"


def test_monitor_label_tags_primary_monitor():
    label = _monitor_label("\\\\.\\DISPLAY2", (1920, 0, 3840, 1080), True)
    assert label == "Display 2 (1920x1080) — Ana Ekran"


def test_find_browser_path_returns_none_for_unknown_browser():
    assert find_browser_path("netscape") is None


def _touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff\xd8img")
    return path


def test_pick_cached_image_finds_header_in_hashed_subfolder(tmp_path):
    """Yeni Steam oyunlarinda gorseller hash'li alt klasorde; CDN'deki eski
    sabit header.jpg adresi 404 veriyor (or. 007 First Light, WARDOGS)."""
    app_dir = tmp_path / "1867240"
    _touch(app_dir / "9e3d" / "library_hero.jpg")
    header = _touch(app_dir / "c499" / "library_header.jpg")
    _touch(app_dir / "31dd" / "library_capsule.jpg")

    assert pick_cached_steam_image(app_dir) == header


def test_pick_cached_image_accepts_localized_capsule_when_no_header(tmp_path):
    app_dir = tmp_path / "3065940"
    _touch(app_dir / "30e5" / "library_hero_turkish.jpg")
    capsule = _touch(app_dir / "1a9b" / "library_capsule_turkish.jpg")
    _touch(app_dir / "a884" / "logo_turkish.png")

    assert pick_cached_steam_image(app_dir) == capsule


def test_pick_cached_image_prefers_flat_header_of_old_layout(tmp_path):
    app_dir = tmp_path / "10"
    header = _touch(app_dir / "header.jpg")
    _touch(app_dir / "library_600x900.jpg")

    assert pick_cached_steam_image(app_dir) == header


def test_pick_cached_image_returns_none_without_images(tmp_path):
    app_dir = tmp_path / "42"
    _touch(app_dir / "abc" / "logo.png")

    assert pick_cached_steam_image(app_dir) is None
    assert pick_cached_steam_image(tmp_path / "missing") is None
