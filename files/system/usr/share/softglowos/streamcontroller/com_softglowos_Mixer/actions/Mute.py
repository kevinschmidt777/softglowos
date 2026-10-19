"""Mutes a channel (stream mix, Me mix or both) or the mic. Shows the state:
crossed-out icon on red while muted."""

from src.backend.DeckManagement.InputIdentifier import Input

from .TargetAction import CLEAR, MUTED_COLOR, TargetAction


class Mute(TargetAction):
    def event_callback(self, event, data=None):
        if event in (Input.Key.Events.DOWN, Input.Dial.Events.DOWN):
            self.toggle()

    def toggle(self):
        # "Both" mutes or unmutes both mixes together, also when they differ
        mute = not self.is_muted()
        for target in self.targets():
            if bool(self.hub.state(f'mute-{target}')) != mute:
                self.hub.toggle_mute(target)

    def redraw(self):
        muted = self.is_muted()
        self.set_media(media_path=self.speaker_icon(muted), size=0.7)
        self.set_background_color(MUTED_COLOR if muted else CLEAR)
        self.labels()
