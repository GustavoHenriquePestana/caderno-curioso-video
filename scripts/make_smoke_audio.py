"""Gera o áudio sintético do episódio de teste: um "som de palavra" (tom harmônico com
envelope) em cada intervalo de timing/words.json, silêncio no resto. Não é voz.

    python scripts/make_smoke_audio.py [episodes/_smoke]
"""
from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np

RATE = 48000


def build(words, duration, rate=RATE):
    n = int(round(duration * rate))
    out = np.zeros(n, dtype=np.float64)
    for k, w in enumerate(words):
        a, b = int(w["start"] * rate), int(w["end"] * rate)
        t = np.arange(b - a) / rate
        f0 = 150 + 25 * (k % 3)
        tone = sum(np.sin(2 * np.pi * f0 * h * t) / h for h in range(1, 6))
        env = np.minimum(1, np.minimum(t / 0.02, (t[-1] - t) / 0.03 + 1e-9))
        env *= 0.8 + 0.2 * np.sin(2 * np.pi * 5 * t)  # sílabas
        out[a:b] += 0.25 * tone * env
    return out


def main(episode="episodes/_smoke"):
    ep = Path(episode)
    import yaml
    spec = yaml.safe_load((ep / "episode.yaml").read_text(encoding="utf-8"))
    words = json.loads((ep / spec["timing"]).read_text(encoding="utf-8"))["narracao"]
    duration = float(spec["scenes"][-1]["end"])
    samples = build(words, duration)
    dest = ep / spec["audio"]["tracks"][0]["file"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(str(dest), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(pcm.tobytes())
    print(dest)


if __name__ == "__main__":
    main(*sys.argv[1:])
