from macrodeck import autostart


def test_is_supported_false_in_dev_mode():
    # testler her zaman gelistirme (frozen olmayan) modda calisir
    assert autostart.is_supported() is False


def test_set_enabled_is_noop_when_unsupported():
    # frozen degilken registry'ye hic dokunmamali, exception atmamali
    autostart.set_enabled(True)
    autostart.set_enabled(False)
