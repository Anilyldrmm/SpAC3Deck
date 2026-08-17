from macrodeck.qr import generate_deck_url, generate_qr_png


def test_generate_deck_url_format():
    url = generate_deck_url("192.168.1.10", 8765, "1234")
    assert url == "http://192.168.1.10:8765/deck?token=1234"


def test_generate_qr_png_returns_nonempty_bytes():
    png_bytes = generate_qr_png("http://192.168.1.10:8765/deck?token=1234")
    assert isinstance(png_bytes, bytes)
    assert len(png_bytes) > 0
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
