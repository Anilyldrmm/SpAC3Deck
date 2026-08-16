# MacroDeck — Design Spec

Date: 2026-08-16

## Amaç

Telefondan PC'yi kontrol eden, ücretli StreamDeck/macrodeck donanımına alternatif, saf yazılım bir sistem. Discord, Voicemeeter, Steam ve genel hotkey/uygulama başlatma aksiyonlarını destekler. PC tarafında StreamDeck'in resmi yazılımına benzer bir configurator app ile butonlar tanımlanır; telefon sadece bu config'e göre render edilen bir grid'i gösterip dokunuşları PC'ye iletir.

## Kapsam dışı (v1)

- iOS/Android native app — telefon tarafı PWA (tarayıcı üzerinden "add to home screen")
- İnternet üzerinden uzaktan erişim — sadece LAN
- OBS, Spotify vb. diğer entegrasyonlar — v1'de yok, mimari sonradan eklemeye açık (bkz. Genişletilebilirlik)

## Mimari

```
[Telefon tarayıcı] <--WebSocket/HTTP--> [PC Backend Server] <--> [Voicemeeter / Discord / Steam / OS]
                                              ^
                                              |
                                    [PC Configurator App]
                                    (native pencere, pywebview)
```

Tek Python process, üç bileşen:

1. **Backend server** — FastAPI + WebSocket, arka planda `pystray` ile tray icon olarak çalışır.
2. **PC Configurator app** — `pywebview` ile native pencere, backend'in servis ettiği HTML/JS config arayüzünü sarmalar.
3. **Phone deck view** — backend'in servis ettiği, mobil tarayıcıda açılan responsive grid (PWA).

Stack Python: Voicemeeter (`voicemeeter-api`), sistem sesi (`pycaw`), hotkey simulation (`keyboard`), UI automation (`pywinauto`), tray (`pystray`), native pencere (`pywebview`), QR (`qrcode`), server (`fastapi` + `uvicorn` + websockets).

## Bileşenler

### 1. Backend server

- Config dosyasını (`config/deck.json`) okur/yazar.
- WebSocket endpoint: telefon buton basışlarını gönderir (`{page, button_id, event: press|release}`), backend action handler'ı çalıştırır.
- Durum senkronu: mute/gain/routing state değiştiğinde (kendi aksiyonumuzdan ya da Voicemeeter'da harici değişiklikten) bağlı tüm client'lara WS üzerinden push eder — buton UI'ları güncel kalır.
- REST endpoint: config'i configurator app'e/deck view'a serve eder, PIN doğrulama.

**Action handler tipleri:**

| Tip | Parametreler | Uygulama |
|---|---|---|
| `hotkey` | `keys: string[]` | `keyboard.send()` ile tuş kombinasyonu simüle et |
| `hotkey_hold` | `keys: string[]` | press'te `keyboard.press()`, release'te `keyboard.release()` (PTT için) |
| `voicemeeter_mute` | `strip_index: int` | `voicemeeter-api` strip mute toggle |
| `voicemeeter_gain` | `strip_index: int, value: float` | strip gain set, slider'dan throttle'lı gelir |
| `voicemeeter_route` | `strip_index: int, bus: "A1"\|"A2"\|"A3"\|"B1"\|"B2"\|"B3"` | strip'in ilgili bus routing bool'unu toggle et |
| `steam_launch` | `appid: string` | `os.startfile("steam://run/<appid>")` |
| `discord_screenshare` | `monitor_index: int` (best-effort) | `pywinauto` ile Discord penceresinde share button + monitor seçimi otomasyonu |
| `launch_app` | `path: string` | genel uygulama başlatma (genişletilebilirlik için, v1'de UI'da opsiyonel) |

**Discord mute/deafen:** Discord ayarlarında kullanıcının tanımladığı global kısayol config'e `hotkey` olarak girilir, backend bunu simüle eder. Token/ToS riski yok.

**Discord screenshare caveat:** Discord'da ekran paylaşımı için native global hotkey yok. `pywinauto` ile UI automation kullanılacak — Discord penceresi odakta/açık olmalı, UI güncellemesinde kırılabilir. v1'de best-effort, çalışmazsa fallback: sadece share picker'ı açıp ekran seçimini kullanıcıya bırakmak.

### 2. PC Configurator app

- `pywebview` native pencere, backend'in `/configure` route'unu render eder.
- Sayfa (page) ekle/sil, sayfa içinde buton ekle/sil/sırala.
- Buton düzenleme: label, ikon (emoji picker veya resim upload), aksiyon tipi seç + parametreleri doldur (örn. Voicemeeter strip index + bus checkbox'ları, Steam appid, hotkey combo capture).
- Kaydet → `config/deck.json` güncellenir → tüm bağlı phone client'lara WS üzerinden reload sinyali.
- QR kod gösterimi: `http://<lan-ip>:<port>/deck?token=<pin>` encode edilir, telefon kamerayla okutup direkt bağlanır.

### 3. Phone deck view

- `/deck` route, PIN ile korunur (ilk bağlantıda PIN girilir, localStorage'da tutulur).
- Config'e göre grid render: sayfa sekmeleri, butonlar (ikon+label), basılı/aktif state (mute kırmızı, routing aktif highlight, gain slider).
- Tap → WS'ye press event gönder. Hold-gerektiren aksiyonlar (PTT) için touchstart/touchend ayrımı.
- PWA manifest + service worker: "add to home screen" ile app ikonu gibi açılır.

## Config formatı (özet)

```json
{
  "pages": [
    {
      "name": "Genel",
      "buttons": [
        {"id": "discord-mute", "label": "Mute", "icon": "🎙️", "action": "hotkey", "params": {"keys": ["ctrl","shift","m"]}},
        {"id": "vm-strip1-mute", "label": "Mic", "icon": "🔇", "action": "voicemeeter_mute", "params": {"strip_index": 0}},
        {"id": "vm-strip1-gain", "label": "Mic Gain", "icon": "🎚️", "action": "voicemeeter_gain", "params": {"strip_index": 0}},
        {"id": "vm-strip1-a1", "label": "→A1", "icon": "🔀", "action": "voicemeeter_route", "params": {"strip_index": 0, "bus": "A1"}},
        {"id": "steam-valorant", "label": "Valorant", "icon": "🎮", "action": "steam_launch", "params": {"appid": "1234567"}}
      ]
    }
  ]
}
```

## Güvenlik

- Sadece LAN üzerinde çalışır, internete açılmaz.
- PIN korumalı bağlantı: configurator app her başlatıldığında rastgele PIN üretir/tray'de gösterir (ya da sabitlenebilir), telefon ilk bağlantıda girer.

## Genişletilebilirlik

Action handler'lar registry pattern ile eklenir (`actions/registry.py` içinde `@register("type_name")`), yeni entegrasyon (OBS, Spotify vb.) eklemek yeni bir handler dosyası + config UI'da yeni parametre şeması eklemek kadar basit olacak şekilde tasarlanır.

## Test planı

1. Backend + configurator'ı başlat.
2. Discord mute/deafen butonu ekle, gerçek Discord ile test et.
3. Discord screenshare butonu ekle, best-effort davranışı doğrula.
4. Voicemeeter strip için mute + gain slider + A1/B1 routing butonları ekle, Voicemeeter Banana/Potato ile canlı test et.
5. Steam launch butonu ekle, gerçek appid ile test et.
6. Telefon tarayıcısından QR ile bağlan, tüm butonları LAN üzerinden dene, state senkronunu doğrula (PC'de manuel Voicemeeter değişikliği telefon UI'a yansımalı).
