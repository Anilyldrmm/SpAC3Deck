# MacroDeck

Telefondan LAN üzerinden PC kontrolü: Discord, Voicemeeter, Steam ve genel hotkey/uygulama başlatma.

## Kurulum (kullanıcılar için)

1. [Releases](https://github.com/Anilyldrmm/SpAC3Deck/releases/latest) sayfasından **MacroDeckSetup.exe** dosyasını indir.
2. Çalıştır, "İleri" sihirbazını takip et — yönetici izni istemez, birkaç saniyede kurulur.
3. Kurulum bitince açılan MacroDeck penceresinde (ya da tray'deki simgeden "Configurator Aç") gösterilen QR kodu telefonla okut, ya da Deck URL'sini aynı WiFi'daki telefonun tarayıcısında aç.

Program arka planda (tray'de) çalışmaya devam eder; kapatmak için tray simgesine sağ tıklayıp "Çıkış" seç. Yeni sürümler otomatik olarak (arka planda, sessizce) indirilip uygulanır — elle bir şey yapmana gerek yok.

## Geliştirme

```bash
pip install -r requirements.txt
python -m macrodeck.main
```

### Test

```bash
pytest
```

### Config

`config/deck.json` — configurator penceresinden (tray → "Configurator Aç") ya da doğrudan dosyayı düzenleyerek değiştirilir. (Paketlenmiş `.exe` ile çalıştırılıyorsa bu dosya `%APPDATA%\MacroDeck\deck.json` konumundadır — kurulum yeri olan `%LOCALAPPDATA%\Programs\MacroDeck\`'ten farklıdır.)

### Paketleme (installer üretme)

```bash
pip install -r requirements.txt
pyinstaller MacroDeck.spec
"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" installer.iss
```

İlk komut `dist/MacroDeck/` klasörünü (exe + `_internal/`) üretir, ikincisi bunu tek bir `dist/installer/MacroDeckSetup.exe` kurulum dosyasına paketler. Yeni bir sürüm yayınlarken `macrodeck/__init__.py`'deki `__version__` ile `installer.iss`'teki `MyAppVersion`'ı birlikte güncelle. Config, bridge token, ikon/ses cache'i `%APPDATA%\MacroDeck\` altına yazılır (kurulum yerinden bağımsız, salt-okunur bir klasöre kurulsa bile sorun çıkmaz).

Otomatik güncelleme (`macrodeck/updater.py`) GitHub Releases'teki `MacroDeck-win64.zip` + `SHA256SUMS.txt` asset'lerini kullanır — bunlar installer'dan ayrı bir mekanizma, her release'e ikisi de eklenmeli:

```bash
cd dist/MacroDeck && powershell Compress-Archive -Path * -DestinationPath ../../MacroDeck-win64.zip
cd ../.. && sha256sum MacroDeck-win64.zip  # -> SHA256SUMS.txt ("<hash>  MacroDeck-win64.zip")
gh release create vX.Y.Z MacroDeck-win64.zip SHA256SUMS.txt dist/installer/MacroDeckSetup.exe
```

## End-to-End Manual Test Checklist

1. `python -m macrodeck.main` çalıştır, tray icon'un göründüğünü doğrula.
2. Configurator penceresinin açıldığını, `config/deck.json`'daki sayfa/butonların göründüğünü doğrula.
3. Gerçek Discord açıkken mute/deafen butonlarını (configurator'dan test edip) telefon deck'inden tetikle, Discord'da mikrofon/ses durumunun değiştiğini doğrula.
4. Discord ekran paylaşımı butonuna bas, best-effort automation'ın çalışıp çalışmadığını doğrula; çalışmazsa `discord_automation.py`'deki selector'ları gerçek Discord sürümüne göre güncelle.
5. Gerçek Voicemeeter (Banana/Potato) açıkken mute, gain slider, A1/B1 routing butonlarını telefon deck'inden test et; PC'de Voicemeeter arayüzünden manuel mute değişikliği yap, telefon UI'ın state broadcast ile güncellendiğini doğrula.
6. Steam açıkken gerçek bir appid ile oyun launch butonunu test et.
7. Telefonu farklı bir cihazdan (yanlış PIN ile) bağlanmayı dene, reddedildiğini doğrula.
8. Telefon tarayıcısında "add to home screen" yap, PWA ikonunun oluştuğunu doğrula.
