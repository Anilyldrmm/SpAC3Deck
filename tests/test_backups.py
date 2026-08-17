import time

from macrodeck.backups import create_backup, list_backups, restore_backup, MAX_BACKUPS


def test_create_backup_copies_existing_file(tmp_path):
    config_path = tmp_path / "deck.json"
    config_path.write_text('{"pages": []}', encoding="utf-8")

    create_backup(config_path)

    backups = list_backups(config_path)
    assert len(backups) == 1


def test_create_backup_noop_when_config_missing(tmp_path):
    config_path = tmp_path / "deck.json"
    create_backup(config_path)
    assert list_backups(config_path) == []


def test_prunes_old_backups_beyond_max(tmp_path):
    config_path = tmp_path / "deck.json"
    config_path.write_text('{"pages": []}', encoding="utf-8")

    for _ in range(MAX_BACKUPS + 5):
        create_backup(config_path)
        time.sleep(0.01)  # dosya adlarinin (timestamp) benzersiz olmasi icin

    assert len(list_backups(config_path)) == MAX_BACKUPS


def test_restore_backup_copies_content_back(tmp_path):
    config_path = tmp_path / "deck.json"
    config_path.write_text('{"pages": [{"name": "A", "buttons": []}]}', encoding="utf-8")
    create_backup(config_path)
    backup_filename = list_backups(config_path)[0]["filename"]

    config_path.write_text('{"pages": []}', encoding="utf-8")

    assert restore_backup(config_path, backup_filename) is True
    assert "A" in config_path.read_text(encoding="utf-8")


def test_restore_backup_rejects_missing_file(tmp_path):
    config_path = tmp_path / "deck.json"
    config_path.write_text('{"pages": []}', encoding="utf-8")
    assert restore_backup(config_path, "does_not_exist.json") is False


def test_restore_backup_ignores_path_traversal(tmp_path):
    config_path = tmp_path / "deck.json"
    config_path.write_text('{"pages": []}', encoding="utf-8")
    assert restore_backup(config_path, "../../../windows/system32/calc.exe") is False
