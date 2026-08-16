# MacroDeck

Telefondan LAN üzerinden PC kontrolü: Discord, Voicemeeter, Steam ve genel hotkey/uygulama başlatma.

## Kurulum

```bash
pip install -r requirements.txt
python -m macrodeck.main
```

Konsolda basılan Deck URL'sini telefonda tarayıcıyla aç (aynı WiFi ağında olmalısın) ya da configurator penceresindeki QR kodu okut.

## Test

```bash
pytest
```

## Config

`config/deck.json` — configurator penceresinden (tray → "Configurator Aç") ya da doğrudan dosyayı düzenleyerek değiştirilir.

## End-to-End Manual Test Checklist

1. `python -m macrodeck.main` çalıştır, tray icon'un göründüğünü doğrula.
2. Configurator penceresinin açıldığını, `config/deck.json`'daki sayfa/butonların göründüğünü doğrula.
3. Gerçek Discord açıkken mute/deafen butonlarını (configurator'dan test edip) telefon deck'inden tetikle, Discord'da mikrofon/ses durumunun değiştiğini doğrula.
4. Discord ekran paylaşımı butonuna bas, best-effort automation'ın çalışıp çalışmadığını doğrula; çalışmazsa `discord_automation.py`'deki selector'ları gerçek Discord sürümüne göre güncelle.
5. Gerçek Voicemeeter (Banana/Potato) açıkken mute, gain slider, A1/B1 routing butonlarını telefon deck'inden test et; PC'de Voicemeeter arayüzünden manuel mute değişikliği yap, telefon UI'ın state broadcast ile güncellendiğini doğrula.
6. Steam açıkken gerçek bir appid ile oyun launch butonunu test et.
7. Telefonu farklı bir cihazdan (yanlış PIN ile) bağlanmayı dene, reddedildiğini doğrula.
8. Telefon tarayıcısında "add to home screen" yap, PWA ikonunun oluştuğunu doğrula.
