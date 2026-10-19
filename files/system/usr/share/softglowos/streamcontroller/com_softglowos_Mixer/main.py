"""SoftglowOS Mixer for StreamController: mute channels and the mic and
change their volume, through the SoftglowOS Hub (works with a GoXLR too)."""

import weakref

from src.backend.PluginManager.PluginBase import PluginBase
from src.backend.PluginManager.ActionHolder import ActionHolder
from src.backend.PluginManager.ActionInputSupport import ActionInputSupport
from src.backend.DeckManagement.InputIdentifier import Input

from .actions.Mute import Mute
from .actions.Volume import Volume
from .hub_client import HubClient
from .texts import t


class SoftglowMixer(PluginBase):
    def __init__(self):
        super().__init__()
        self.hub = HubClient()
        self._watchers = weakref.WeakSet()
        self.hub.listen(self._on_hub_state)

        support = {
            Input.Key: ActionInputSupport.SUPPORTED,
            Input.Dial: ActionInputSupport.SUPPORTED,
            Input.Touchscreen: ActionInputSupport.UNSUPPORTED,
        }
        self.add_action_holder(ActionHolder(
            plugin_base=self, action_base=Mute, action_id_suffix='Mute',
            action_name=t('mute'), action_support=support))
        self.add_action_holder(ActionHolder(
            plugin_base=self, action_base=Volume, action_id_suffix='Volume',
            action_name=t('volume'), action_support=support))

        self.register(
            plugin_name=t('plugin'),
            github_repo='https://github.com/kevinschmidt777/softglowos',
            plugin_version='1.0.0',
            app_version='1.5.0-beta.16',
        )

    def watch(self, action):
        """Redraws the action whenever the Hub reports a change."""
        self._watchers.add(action)

    def _on_hub_state(self, name, _value):
        for action in list(self._watchers):
            action.on_hub_state(name)
