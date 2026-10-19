"""German or English, like the rest of SoftglowOS."""

import locale
import os

GERMAN = (os.environ.get('LANG') or locale.getlocale()[0] or '').startswith('de')

_TEXTS = {
    'plugin': ('SoftglowOS Mixer', 'SoftglowOS Mixer'),
    'mute': ('Mute', 'Stummschalten'),
    'volume': ('Volume', 'Lautstärke'),
    'target': ('Channel', 'Kanal'),
    'mix': ('Mix', 'Mix'),
    'direction': ('Key press', 'Tastendruck'),
    'up': ('Louder', 'Lauter'),
    'down': ('Quieter', 'Leiser'),
    'step': ('Step (%)', 'Schritt (%)'),
    'mic': ('Microphone', 'Mikrofon'),
    'game': ('Game', 'Game'),
    'chat': ('Chat', 'Chat'),
    'music': ('Music', 'Musik'),
    'system': ('System', 'System'),
    'browser': ('Browser', 'Browser'),
    'console': ('Console', 'Konsole'),
    'stream': ('Stream', 'Stream'),
    'monitor': ('Me', 'Ich'),
    'both': ('Both', 'Beide'),
}


def t(key):
    english, german = _TEXTS[key]
    return german if GERMAN else english
