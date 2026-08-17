from macrodeck.sources import parse_appmanifest, parse_library_folders, _monitor_label, find_browser_path


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
