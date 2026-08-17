from macrodeck.discord_screenshare import DiscordScreenShareController
from macrodeck.actions.registry import dispatch
from macrodeck.actions.context import ActionContext
import macrodeck.actions.discord  # noqa: F401


class FakeAutomation:
    def __init__(self):
        self.calls = []
        self.stop_calls = 0
        self.join_calls = []
        self.leave_calls = 0
        self.camera_toggle_calls = 0

    def toggle_share(self, monitor_index: int) -> None:
        self.calls.append(monitor_index)

    def toggle_stream_sound(self) -> None:
        pass

    def stop_share(self) -> None:
        self.stop_calls += 1

    def join_channel(self, guild_id: str, channel_id: str) -> None:
        self.join_calls.append((guild_id, channel_id))

    def leave_channel(self) -> None:
        self.leave_calls += 1

    def toggle_camera(self) -> None:
        self.camera_toggle_calls += 1


def test_controller_forwards_monitor_index():
    automation = FakeAutomation()
    controller = DiscordScreenShareController(automation)
    controller.share_monitor(1)
    assert automation.calls == [1]


def test_dispatch_discord_screenshare_action():
    automation = FakeAutomation()
    controller = DiscordScreenShareController(automation)
    context = ActionContext(
        send_hotkey=lambda keys: None,
        hold_key=lambda keys: None,
        release_key=lambda keys: None,
        launch_uri=lambda uri: None,
        voicemeeter=None,
        screenshare=controller,
    )
    dispatch("discord_screenshare", {"monitor_index": 0}, context, "press")
    assert automation.calls == [0]


def test_dispatch_discord_stop_share_action():
    automation = FakeAutomation()
    controller = DiscordScreenShareController(automation)
    context = ActionContext(
        send_hotkey=lambda keys: None,
        hold_key=lambda keys: None,
        release_key=lambda keys: None,
        launch_uri=lambda uri: None,
        voicemeeter=None,
        screenshare=controller,
    )
    dispatch("discord_stop_share", {}, context, "press")
    assert automation.stop_calls == 1


def test_dispatch_discord_join_channel_action():
    automation = FakeAutomation()
    controller = DiscordScreenShareController(automation)
    context = ActionContext(
        send_hotkey=lambda keys: None,
        hold_key=lambda keys: None,
        release_key=lambda keys: None,
        launch_uri=lambda uri: None,
        voicemeeter=None,
        screenshare=controller,
    )
    dispatch("discord_join_channel", {"guild_id": "g1", "channel_id": "c1"}, context, "press")
    assert automation.join_calls == [("g1", "c1")]


def test_dispatch_discord_leave_channel_action():
    automation = FakeAutomation()
    controller = DiscordScreenShareController(automation)
    context = ActionContext(
        send_hotkey=lambda keys: None,
        hold_key=lambda keys: None,
        release_key=lambda keys: None,
        launch_uri=lambda uri: None,
        voicemeeter=None,
        screenshare=controller,
    )
    dispatch("discord_leave_channel", {}, context, "press")
    assert automation.leave_calls == 1


def test_dispatch_discord_camera_toggle_action():
    automation = FakeAutomation()
    controller = DiscordScreenShareController(automation)
    context = ActionContext(
        send_hotkey=lambda keys: None,
        hold_key=lambda keys: None,
        release_key=lambda keys: None,
        launch_uri=lambda uri: None,
        voicemeeter=None,
        screenshare=controller,
    )
    dispatch("discord_camera_toggle", {}, context, "press")
    assert automation.camera_toggle_calls == 1
