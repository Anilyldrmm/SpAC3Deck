import hashlib
import json
import zipfile

import pytest

from macrodeck import updater


class FakeResponse:
    def __init__(self, data: bytes):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *_args):
        data, self._data = self._data, b""
        return data


def _fake_urlopen(responses):
    """URL -> bytes eslemesinden sirali cagrilarda dogru FakeResponse'u doner."""

    def _urlopen(request, timeout=None):
        url = request.full_url if hasattr(request, "full_url") else request
        return FakeResponse(responses[url])

    return _urlopen


def test_parse_version_ignores_v_prefix():
    assert updater._parse_version("v1.2.3") == (1, 2, 3)


def test_parse_version_handles_garbage_as_zero():
    assert updater._parse_version("not-a-version") == (0,)


def test_is_newer_true_when_remote_greater():
    assert updater.is_newer("v2.0.0", current="1.0.0") is True


def test_is_newer_false_when_equal_or_older():
    assert updater.is_newer("v1.0.0", current="1.0.0") is False
    assert updater.is_newer("v0.9.0", current="1.0.0") is False


def test_check_for_update_returns_info_when_newer(monkeypatch):
    release = {
        "tag_name": "v2.0.0",
        "assets": [
            {"name": updater.ASSET_NAME, "browser_download_url": "https://example/asset.zip"},
            {"name": updater.CHECKSUMS_NAME, "browser_download_url": "https://example/sums.txt"},
        ],
    }
    checksums_text = f"deadbeef  {updater.ASSET_NAME}\n"
    responses = {
        updater._API_URL: json.dumps(release).encode("utf-8"),
        "https://example/sums.txt": checksums_text.encode("utf-8"),
    }
    monkeypatch.setattr(updater.urllib.request, "urlopen", _fake_urlopen(responses))

    info = updater.check_for_update(current_version="1.0.0")

    assert info is not None
    assert info.version == "v2.0.0"
    assert info.download_url == "https://example/asset.zip"
    assert info.sha256 == "deadbeef"


def test_check_for_update_returns_none_when_not_newer(monkeypatch):
    release = {"tag_name": "v1.0.0", "assets": []}
    responses = {updater._API_URL: json.dumps(release).encode("utf-8")}
    monkeypatch.setattr(updater.urllib.request, "urlopen", _fake_urlopen(responses))

    assert updater.check_for_update(current_version="1.0.0") is None


def test_check_for_update_returns_none_when_asset_missing(monkeypatch):
    release = {"tag_name": "v2.0.0", "assets": []}
    responses = {updater._API_URL: json.dumps(release).encode("utf-8")}
    monkeypatch.setattr(updater.urllib.request, "urlopen", _fake_urlopen(responses))

    assert updater.check_for_update(current_version="1.0.0") is None


def test_check_for_update_returns_none_on_network_error(monkeypatch):
    def _raise(*_args, **_kwargs):
        raise updater.urllib.error.URLError("no network")

    monkeypatch.setattr(updater.urllib.request, "urlopen", _raise)

    assert updater.check_for_update(current_version="1.0.0") is None


def test_verify_sha256_matches(tmp_path):
    path = tmp_path / "file.bin"
    path.write_bytes(b"hello world")
    expected = hashlib.sha256(b"hello world").hexdigest()

    assert updater.verify_sha256(path, expected) is True
    assert updater.verify_sha256(path, "0" * 64) is False


def test_extract_zip_writes_contents_and_clears_previous(tmp_path):
    zip_path = tmp_path / "update.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("MacroDeck.exe", "binary-stub")

    dest = tmp_path / "staging"
    dest.mkdir()
    (dest / "stale.txt").write_text("old", encoding="utf-8")

    updater.extract_zip(zip_path, dest)

    assert (dest / "MacroDeck.exe").read_text(encoding="utf-8") == "binary-stub"
    assert not (dest / "stale.txt").exists()


def test_build_apply_script_contains_pid_and_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "app_data_dir", lambda: tmp_path)
    staging = tmp_path / "staging"
    target = tmp_path / "install"

    script_path = updater.build_apply_script(staging, target, "MacroDeck.exe", pid=4242)

    content = script_path.read_text(encoding="utf-8")
    assert "4242" in content
    assert str(staging) in content
    assert str(target) in content
    assert "robocopy" in content
    assert "MacroDeck.exe" in content


def test_download_file_writes_bytes(monkeypatch, tmp_path):
    responses = {"https://example/asset.zip": b"payload-bytes"}
    monkeypatch.setattr(updater.urllib.request, "urlopen", _fake_urlopen(responses))

    dest = tmp_path / "nested" / "asset.zip"
    updater.download_file("https://example/asset.zip", dest)

    assert dest.read_bytes() == b"payload-bytes"


def test_run_update_loop_stops_immediately_when_quitting():
    import threading

    quitting = threading.Event()
    quitting.set()
    called = []

    updater.run_update_loop(quitting, lambda: called.append(True))

    assert called == []


def test_run_update_loop_applies_update_then_stops(monkeypatch):
    import threading

    quitting = threading.Event()
    info = updater.UpdateInfo(version="v2.0.0", download_url="url", sha256="sha")

    monkeypatch.setattr(updater, "STARTUP_DELAY_SECONDS", 0)
    monkeypatch.setattr(updater, "check_for_update", lambda: info)
    monkeypatch.setattr(updater, "apply_update", lambda i: True)

    applied = []
    updater.run_update_loop(quitting, lambda: applied.append(True))

    assert applied == [True]
