/**
 * @name MacroDeckBridge
 * @author SpAC3
 * @version 1.0.0
 * @description MacroDeck backend'inden gelen "go_live" komutlariyla ekran paylasimini
 * Discord'un kendi internal modulleri uzerinden baslatir (UI automation yerine).
 */

module.exports = class MacroDeckBridge {
    constructor() {
        this.socket = null;
        this.reconnectTimer = null;
        this.reconnectDelay = 1000;
        this.maxReconnectDelay = 15000;
        this.stopped = false;
        this.statusInterval = null;
        this.lastStatus = { streaming: null, sound: null, camera: null };
    }

    getDefaultConfig() {
        return { host: "127.0.0.1", port: 8765, token: "" };
    }

    loadConfig() {
        return Object.assign(this.getDefaultConfig(), BdApi.Data.load("MacroDeckBridge", "config") || {});
    }

    saveConfig(config) {
        BdApi.Data.save("MacroDeckBridge", "config", config);
    }

    start() {
        this.stopped = false;
        this.connect();
    }

    stop() {
        this.stopped = true;
        clearTimeout(this.reconnectTimer);
        clearInterval(this.statusInterval);
        this.statusInterval = null;
        if (this.socket) {
            this.socket.onclose = null;
            this.socket.close();
            this.socket = null;
        }
    }

    connect() {
        if (this.stopped) return;
        const { host, port, token } = this.loadConfig();
        if (!token) {
            console.warn("[MacroDeckBridge] token ayarlanmamis, ayarlar panelinden gir");
            return;
        }

        const url = `ws://${host}:${port}/ws/discord-bridge?token=${encodeURIComponent(token)}`;
        const socket = new WebSocket(url);
        this.socket = socket;

        socket.onopen = () => {
            console.log("[MacroDeckBridge] MacroDeck backend'e baglandi");
            this.reconnectDelay = 1000;
            this.lastStatus = { streaming: null, sound: null, camera: null };
            clearInterval(this.statusInterval);
            this.statusInterval = setInterval(() => this.pushStatus(), 300);
            this.pushStatus();
        };

        socket.onmessage = (event) => {
            let command;
            try {
                command = JSON.parse(event.data);
            } catch (exc) {
                console.error("[MacroDeckBridge] gecersiz komut:", event.data);
                return;
            }
            this.handleCommand(command);
        };

        socket.onclose = () => {
            clearInterval(this.statusInterval);
            this.statusInterval = null;
            if (this.stopped) return;
            this.reconnectTimer = setTimeout(() => this.connect(), this.reconnectDelay);
            this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
        };

        socket.onerror = () => socket.close();
    }

    handleCommand(command) {
        if (command.cmd === "go_live") {
            this.startScreenShare(command.monitor_index ?? 0).catch((exc) => {
                console.error("[MacroDeckBridge] go_live basarisiz:", exc);
            });
        } else if (command.cmd === "toggle_stream_sound") {
            try {
                this.toggleStreamSound();
            } catch (exc) {
                console.error("[MacroDeckBridge] toggle_stream_sound basarisiz:", exc);
            }
        } else if (command.cmd === "stop_share") {
            // STREAM_STOP'u yalniz basina dispatch etmek Discord'u crash ediyordu.
            // Guvenli alternatif: kanaldan cik + geri gir, RTC sifirlanirken yayin
            // da dogal olarak sonlanir.
            try {
                this.restartVoiceConnection();
            } catch (exc) {
                console.error("[MacroDeckBridge] stop_share basarisiz:", exc);
            }
        } else if (command.cmd === "join_channel") {
            try {
                this.joinChannel(command.guild_id, command.channel_id);
            } catch (exc) {
                console.error("[MacroDeckBridge] join_channel basarisiz:", exc);
            }
        } else if (command.cmd === "leave_channel") {
            try {
                this.leaveChannel();
            } catch (exc) {
                console.error("[MacroDeckBridge] leave_channel basarisiz:", exc);
            }
        } else if (command.cmd === "toggle_camera") {
            try {
                this.toggleCamera();
            } catch (exc) {
                console.error("[MacroDeckBridge] toggle_camera basarisiz:", exc);
            }
        }
    }

    /**
     * Kendi ses kanalindaki gercek kamera durumunu okur. MediaEngineStore'da
     * bunun icin guvenilir bir getter yok (isSelfVideo tanimli degil, hasVideo
     * yanlis deger donuyor) - VoiceStateStore'daki kendi voice state'inin
     * selfVideo alani gercek zamanli ve dogru kaynak.
     */
    getSelfVideoState() {
        const UserStore = BdApi.Webpack.getStore("UserStore");
        const VoiceStateStore = BdApi.Webpack.getStore("VoiceStateStore");
        const myId = UserStore?.getCurrentUser?.()?.id;
        if (!myId) return false;
        return Boolean(VoiceStateStore?.getVoiceStateForUser?.(myId)?.selfVideo);
    }

    /** Kamerayi acar/kapatir (MEDIA_ENGINE_SET_VIDEO_ENABLED). Discord'un kendi onay/onizleme ekranini atlar. */
    toggleCamera() {
        const StreamStore = BdApi.Webpack.getStore("ApplicationStreamingStore");
        if (!StreamStore?._dispatcher) {
            throw new Error("dispatcher bulunamadi");
        }
        const next = !this.getSelfVideoState();
        this.lastStatus.camera = next;
        StreamStore._dispatcher.dispatch({ type: "MEDIA_ENGINE_SET_VIDEO_ENABLED", enabled: next });
    }

    /** Ses kanalina gir/kanal degistir (VOICE_CHANNEL_SELECT, guild sesli kanallari icin). */
    joinChannel(guildId, channelId) {
        const ChannelStore = BdApi.Webpack.getStore("SelectedChannelStore");
        const StreamStore = BdApi.Webpack.getStore("ApplicationStreamingStore");
        if (!StreamStore?._dispatcher) {
            throw new Error("dispatcher bulunamadi");
        }
        const currentVoiceChannelId = ChannelStore?.getVoiceChannelId?.() ?? null;
        StreamStore._dispatcher.dispatch({
            type: "VOICE_CHANNEL_SELECT",
            guildId,
            channelId,
            currentVoiceChannelId,
            video: false,
            stream: false,
            lockVoiceStateForResume: false,
            joinVoiceId: crypto.randomUUID(),
            bypassIdleUpdate: false,
        });
    }

    /** Aktif ses kanalindan cikar (VOICE_CHANNEL_SELECT, channelId: null). */
    leaveChannel() {
        const ChannelStore = BdApi.Webpack.getStore("SelectedChannelStore");
        const StreamStore = BdApi.Webpack.getStore("ApplicationStreamingStore");
        if (!StreamStore?._dispatcher) {
            throw new Error("dispatcher bulunamadi");
        }
        const currentVoiceChannelId = ChannelStore?.getVoiceChannelId?.() ?? null;
        if (!currentVoiceChannelId) return;
        StreamStore._dispatcher.dispatch({
            type: "VOICE_CHANNEL_SELECT",
            channelId: null,
            currentVoiceChannelId,
            video: false,
            stream: false,
            lockVoiceStateForResume: false,
            joinVoiceId: crypto.randomUUID(),
            bypassIdleUpdate: false,
        });
    }

    /**
     * Bulundugu ses kanalindan cikip ayni kanala geri girer. Ekran paylasimini
     * "durdurmanin" guvenli yolu: RTC baglantisi tamamen sifirlanir, yayin da
     * bu sirada dogal olarak sonlanir (STREAM_STOP'u yalniz dispatch etmenin
     * aksine crash riski yok, tamamen normal join/leave akisi kullanilir).
     */
    restartVoiceConnection() {
        const ChannelStore = BdApi.Webpack.getStore("SelectedChannelStore");
        const GuildStore = BdApi.Webpack.getStore("SelectedGuildStore");
        const channelId = ChannelStore?.getVoiceChannelId?.();
        if (!channelId) {
            throw new Error("aktif bir ses kanalinda degilsin");
        }
        const guildId = GuildStore?.getGuildId?.() ?? null;

        this.leaveChannel();
        setTimeout(() => this.joinChannel(guildId, channelId), 800);
    }

    /**
     * Yayinin sistem sesi paylasimini acar/kapatir. Discord'daki "Yayin Sesini
     * Paylas" checkbox'i ile ayni MEDIA_ENGINE_SET_GO_LIVE_SOURCE action'ini
     * gonderir (STREAM_UPDATE_SETTINGS sadece bir tercih flag'i set ediyor,
     * gercek ses aktarimini bu action tetikliyor). Mevcut kaynak/kaliteyi
     * MediaEngineStore.getGoLiveSource() ile okuyup sadece sesi cevirir.
     */
    toggleStreamSound() {
        const MediaEngineStore = BdApi.Webpack.getStore("MediaEngineStore");
        const SettingsStore = BdApi.Webpack.getStore("ApplicationStreamingSettingsStore");
        const StreamStore = BdApi.Webpack.getStore("ApplicationStreamingStore");
        if (!StreamStore?._dispatcher || !MediaEngineStore || !SettingsStore) {
            throw new Error("store/dispatcher bulunamadi");
        }
        const goLive = MediaEngineStore.getGoLiveSource();
        const settings = SettingsStore.getState();
        if (!goLive?.desktopSource) {
            throw new Error("aktif go-live source bulunamadi (yayin acik degil mi?)");
        }
        const newSound = !settings.soundshareEnabled;

        // Gercek Discord checkbox'i ikisini birden dispatch ediyor: biri durum/UI
        // state'i (STREAM_UPDATE_SETTINGS), digeri native ses aktarimini tetikleyen
        // asil action (MEDIA_ENGINE_SET_GO_LIVE_SOURCE).
        StreamStore._dispatcher.dispatch({
            type: "STREAM_UPDATE_SETTINGS",
            preset: settings.preset,
            resolution: settings.resolution,
            frameRate: settings.fps,
            soundshareEnabled: newSound,
        });
        StreamStore._dispatcher.dispatch({
            type: "MEDIA_ENGINE_SET_GO_LIVE_SOURCE",
            settings: {
                qualityOptions: {
                    preset: settings.preset,
                    resolution: goLive.quality?.resolution ?? settings.resolution,
                    frameRate: goLive.quality?.frameRate ?? settings.fps,
                },
                context: "stream",
                desktopSettings: {
                    sourceId: goLive.desktopSource.id,
                    sound: newSound,
                },
            },
        });
    }

    /** Yayin acik mi ve sesi paylasiliyor mu bilgisini backend'e gonderir (degisince). */
    pushStatus() {
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return;
        const StreamStore = BdApi.Webpack.getStore("ApplicationStreamingStore");
        const SettingsStore = BdApi.Webpack.getStore("ApplicationStreamingSettingsStore");
        const active = StreamStore?.getCurrentUserActiveStream?.();
        const streaming = active?.state === "ACTIVE";
        const sound = Boolean(SettingsStore?.getState?.()?.soundshareEnabled);
        const camera = this.getSelfVideoState();

        if (streaming === this.lastStatus.streaming && sound === this.lastStatus.sound && camera === this.lastStatus.camera) {
            return;
        }
        this.lastStatus = { streaming, sound, camera };
        this.socket.send(
            JSON.stringify({ type: "state", discord_streaming: streaming, discord_sound: sound, discord_camera: camera })
        );
    }

    /**
     * Discord internal Flux Dispatcher'a STREAM_START action'ini dogrudan gonderir
     * (Go Live modal'inin dispatch ettigi payload'la ayni sekilde). Discord
     * guncellemesinde bu action'in alanlari degisirse burasi kirilabilir;
     * devtools'tan (Ctrl+Shift+I) dogrulanip guncellenmesi gerekebilir.
     */
    async startScreenShare(monitorIndex) {
        const sources = await DiscordNative.desktopCapture.getDesktopCaptureSources({
            types: ["screen"],
            thumbnailSize: { width: 0, height: 0 },
        });
        const source = sources[monitorIndex];
        if (!source) {
            throw new Error(`monitor_index ${monitorIndex} icin ekran bulunamadi`);
        }

        const StreamStore = BdApi.Webpack.getStore("ApplicationStreamingStore");
        const SelectedChannelStore = BdApi.Webpack.getStore("SelectedChannelStore");
        const SelectedGuildStore = BdApi.Webpack.getStore("SelectedGuildStore");
        if (!StreamStore?._dispatcher) {
            throw new Error("ApplicationStreamingStore/dispatcher bulunamadi (Discord guncellemesi olmus olabilir)");
        }

        const channelId = SelectedChannelStore?.getVoiceChannelId?.();
        if (!channelId) {
            throw new Error("aktif bir ses kanalinda degilsin");
        }
        const guildId = SelectedGuildStore?.getGuildId?.() ?? null;

        StreamStore._dispatcher.dispatch({
            type: "STREAM_START",
            streamType: guildId ? "guild" : "call",
            guildId,
            channelId,
            appContext: "APP",
            sourceId: source.id,
            sourceName: source.name,
            sourceIcon: "",
            sourcePid: null,
            sound: true,
            previewDisabled: true,
        });

        // STREAM_START, ApplicationStreamingSettingsStore'u (bizim okudugumuz
        // "sesi paylas" state'i) guncellemez - senkron kalsin diye ayrica dispatch
        // ediyoruz, yoksa pushStatus() ilk acilista yanlis/eski deger gonderir.
        const SettingsStore = BdApi.Webpack.getStore("ApplicationStreamingSettingsStore");
        const currentSettings = SettingsStore?.getState?.();
        if (currentSettings) {
            StreamStore._dispatcher.dispatch({
                type: "STREAM_UPDATE_SETTINGS",
                preset: currentSettings.preset,
                resolution: currentSettings.resolution,
                frameRate: currentSettings.fps,
                soundshareEnabled: true,
            });
        }
    }

    getSettingsPanel() {
        const config = this.loadConfig();
        const panel = document.createElement("div");
        panel.style.padding = "8px";

        const makeField = (labelText, key, placeholder) => {
            const label = document.createElement("label");
            label.textContent = labelText;
            label.style.display = "block";
            label.style.marginTop = "8px";

            const input = document.createElement("input");
            input.type = "text";
            input.value = config[key] ?? "";
            input.placeholder = placeholder;
            input.style.width = "100%";
            input.addEventListener("change", () => {
                const current = this.loadConfig();
                current[key] = key === "port" ? Number(input.value) : input.value;
                this.saveConfig(current);
                this.stop();
                this.start();
            });

            label.appendChild(input);
            return label;
        };

        panel.appendChild(makeField("MacroDeck host", "host", "127.0.0.1"));
        panel.appendChild(makeField("MacroDeck port", "port", "8765"));
        panel.appendChild(makeField("Bridge token", "token", "backend konsolunda yazdirilan token"));

        return panel;
    }
};
