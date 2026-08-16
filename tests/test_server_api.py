from fastapi.testclient import TestClient
from macrodeck.config import Button, Page, DeckConfig, save_config
from macrodeck.server import create_app


def build_client(tmp_path, pin="1234"):
    config_path = tmp_path / "deck.json"
    save_config(
        DeckConfig(pages=[Page(name="Genel", buttons=[
            Button(id="b1", label="Mute", action="hotkey", params={"keys": ["ctrl", "m"]})
        ])]),
        config_path,
    )
    app = create_app(config_path=config_path, pin=pin)
    return TestClient(app)


def test_get_config_without_pin_is_forbidden(tmp_path):
    client = build_client(tmp_path)
    response = client.get("/api/config")
    assert response.status_code == 403


def test_get_config_with_correct_pin(tmp_path):
    client = build_client(tmp_path)
    response = client.get("/api/config", params={"token": "1234"})
    assert response.status_code == 200
    assert response.json()["pages"][0]["name"] == "Genel"


def test_put_config_updates_file(tmp_path):
    client = build_client(tmp_path)
    new_config = {"pages": [{"name": "Yeni", "buttons": []}]}
    response = client.put("/api/config", params={"token": "1234"}, json=new_config)
    assert response.status_code == 200

    verify = client.get("/api/config", params={"token": "1234"})
    assert verify.json()["pages"][0]["name"] == "Yeni"
