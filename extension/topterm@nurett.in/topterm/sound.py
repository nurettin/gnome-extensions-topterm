"""Short sounds for terminal events, played from the files named in config.ini's [sounds] section.

Every file is uploaded to the sound server once at startup, so playing one is a single request.
That request still blocks for 10-20 ms, so it is made from a worker thread rather than from the
main loop, where it would delay typing and output.
"""
import glob
import math
import os
import queue
import random
import threading

import gi
from gi.repository import GLib

from topterm.config import Sound, Sounds

# Streaming output prints many lines a second; closer together than this the chirps become a drone.
MIN_GAP_US = {Sound.SHOW: 0, Sound.HIDE: 0, Sound.LINE: 150_000}


class Speaker:
    def __init__(self, sounds: Sounds) -> None:
        self.choices: dict[Sound, list[dict[str, str]]] = {}
        self.played_at = dict.fromkeys(Sound, 0)
        variants = {sound: expand(sound, pattern) for sound, pattern in sounds.files.items()}
        if sounds.volume == 0 or not any(variants.values()):
            return
        # Only needed once a sound is configured, so imported here.
        gi.require_version("GSound", "1.0")
        from gi.repository import GSound

        context = GSound.Context.new(None)
        volume_db = f"{20 * math.log10(sounds.volume / 100):.1f}"
        for sound, paths in variants.items():
            attrs = [
                {
                    GSound.ATTR_EVENT_ID: f"topterm-{sound}-{n}",
                    GSound.ATTR_MEDIA_FILENAME: path,
                    GSound.ATTR_CANBERRA_VOLUME: volume_db,
                }
                for n, path in enumerate(paths)
            ]
            for attr in attrs:
                context.cache(attr)
            if attrs:
                self.choices[sound] = attrs
        self.requests: queue.SimpleQueue[dict[str, str]] = queue.SimpleQueue()
        threading.Thread(target=self._play_requests, args=(context,), daemon=True).start()

    def play(self, sound: Sound) -> None:
        if sound not in self.choices:
            return
        now = GLib.get_monotonic_time()
        if now - self.played_at[sound] < MIN_GAP_US[sound]:
            return
        self.played_at[sound] = now
        # Random rather than in turn: a fixed order repeats as a little tune.
        self.requests.put(random.choice(self.choices[sound]))

    def _play_requests(self, context) -> None:
        while True:
            context.play_simple(self.requests.get(), None)


def expand(sound: Sound, pattern: str) -> list[str]:
    """The files a [sounds] entry names; an empty entry names none."""
    if not pattern:
        return []
    paths = sorted(glob.glob(os.path.expanduser(pattern)))
    if not paths:
        raise FileNotFoundError(f"[sounds] {sound} = {pattern!r} matches no files")
    return paths
