import sys
from pathlib import Path

# Add project root to sys.path so that macrodeck module can be imported
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


@pytest.fixture(autouse=True)
def _no_real_clipboard(monkeypatch):
    # testler gercek Windows panosunu okumasin/yazmasin
    from macrodeck import os_bridge

    monkeypatch.setattr(os_bridge, "get_clipboard_text", lambda: "")
    monkeypatch.setattr(os_bridge, "set_clipboard_text", lambda text: None)
