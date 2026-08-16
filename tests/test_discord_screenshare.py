from macrodeck.discord_screenshare import DiscordScreenShareController
from macrodeck.actions.registry import dispatch
from macrodeck.actions.context import ActionContext
import macrodeck.actions.discord  # noqa: F401


class FakeAutomation:
    def __init__(self):
        self.calls = []

    def toggle_share(self, monitor_index: int) -> None:
        self.calls.append(monitor_index)


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
