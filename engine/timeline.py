"""Linha do tempo: resolve expressões de tempo ancoradas na narração.

Adaptado de reformaProtestante-/pipeline/timeline.py (commit 4b8f111). Ver NOTICE.md.

Formatos aceitos nos YAML de cena (sempre resultam em segundos absolutos do episódio):
  1.5               segundos a partir do início da cena
  "start+0.5"       relativo ao início da cena
  "end-1"           relativo ao fim da cena
  "abs:12.3"        tempo absoluto do episódio
  "w:gelo"          início da palavra falada (1ª ocorrência dentro da cena)
  "w:gelo#2"        2ª ocorrência dentro da cena
  "w:anos.end+0.2"  fim da palavra, mais deslocamento
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path


def norm(word: str) -> str:
    word = unicodedata.normalize("NFKD", word.lower())
    word = "".join(c for c in word if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", word)


class Timeline:
    def __init__(self, episode: dict, root: Path):
        self.fps = int(episode.get("fps", 30))
        self.words: list[dict] = []
        audio = episode.get("audio") or {}
        timing = episode.get("timing")
        raw = json.loads((root / timing).read_text(encoding="utf-8")) if timing else {}
        for track in audio.get("tracks", []):
            offset = float(track.get("start", 0))
            limit = float(track.get("trim_end", 1e9))
            for w in raw.get(track.get("words", ""), []):
                if w["start"] >= limit:
                    continue
                self.words.append({"w": w["w"], "key": norm(w["w"]),
                                   "start": w["start"] + offset, "end": min(w["end"], limit) + offset})
        self.words.sort(key=lambda w: w["start"])
        self.anchors: list[dict] = []  # registro para o QA de sincronização

    def resolve(self, expr, scene_start: float, scene_end: float, label: str = "") -> float:
        if isinstance(expr, (int, float)):
            return scene_start + float(expr)
        expr = str(expr).strip()
        m = re.fullmatch(r"(start|end)\s*([+-]\s*[\d.]+)?", expr)
        if m:
            base = scene_start if m.group(1) == "start" else scene_end
            return base + float((m.group(2) or "0").replace(" ", ""))
        if expr.startswith("abs:"):
            return float(expr[4:])
        m = re.fullmatch(r"w:([^#.+\-\s]+)(?:#(\d+))?(\.end)?\s*([+-]\s*[\d.]+)?", expr)
        if not m:
            raise ValueError(f"expressão de tempo inválida: {expr!r}")
        key, nth = norm(m.group(1)), int(m.group(2) or 1)
        hits = [w for w in self.words
                if w["key"] == key and scene_start - 0.6 <= w["start"] < scene_end]
        if len(hits) < nth:
            raise ValueError(f"palavra {m.group(1)!r} (#{nth}) não encontrada entre "
                             f"{scene_start:.2f}s e {scene_end:.2f}s")
        word = hits[nth - 1]
        offset = float((m.group(4) or "0").replace(" ", ""))
        t = (word["end"] if m.group(3) else word["start"]) + offset
        self.anchors.append({"layer": label, "expr": expr, "word": word["w"],
                             "word_start": word["start"], "word_end": word["end"],
                             "offset": offset, "edge": "end" if m.group(3) else "start", "time": t})
        return t

    def cut_inside_word(self, t: float, tolerance: float = 0.02) -> dict | None:
        """Retorna a palavra cortada se o instante t cair dentro de uma palavra falada."""
        for w in self.words:
            if w["start"] + tolerance < t < w["end"] - tolerance:
                return w
        return None
