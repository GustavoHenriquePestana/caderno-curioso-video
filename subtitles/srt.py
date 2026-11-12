"""Legendas SRT a partir dos tempos por palavra, e validação de arquivos SRT.

Geração adaptada de reformaProtestante-/pipeline/subtitles.py (commit 4b8f111), agora com
no máximo 2 linhas de até 42 caracteres e verificação de caracteres por segundo.

    python -m subtitles.srt episodes/<episódio> [--height 720]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

MAX_LINE = 42
MAX_LINES = 2
MIN_DUR, MAX_DUR = 1.0, 7.0
CPS_WARN, CPS_FAIL = 17.0, 21.0


def stamp(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def parse_stamp(s: str) -> float:
    h, m, rest = s.strip().split(":")
    sec, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000


def split_lines(text: str, limit: int = MAX_LINE) -> list[str]:
    """Quebra em até 2 linhas equilibradas (sem cortar palavras)."""
    if len(text) <= limit:
        return [text]
    words = text.split()
    best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        score = max(len(a), len(b)) + (0 if len(a) <= limit and len(b) <= limit else 1000)
        if best is None or score < best[0]:
            best = (score, [a, b])
    return best[1]


def fits(text: str) -> bool:
    lines = split_lines(text)
    return len(lines) <= MAX_LINES and all(len(x) <= MAX_LINE for x in lines)


def build_cues(words: list[dict]) -> list[tuple[float, float, str]]:
    cues, line = [], []
    for i, w in enumerate(words):
        line.append(w)
        text = " ".join(x["w"] for x in line)
        nxt = words[i + 1] if i + 1 < len(words) else None
        gap = nxt["start"] - w["end"] if nxt else 9
        nxt_text = f"{text} {nxt['w']}" if nxt else text
        end_sentence = w["w"][-1] in ".?!…"
        soft_break = len(text) >= 45 and w["w"][-1] in ",;:—"
        full = not fits(nxt_text)
        if end_sentence or soft_break or full or gap > 0.8 or nxt is None:
            cues.append((line[0]["start"], w["end"], text))
            line = []
    out = []
    for n, (start, end, text) in enumerate(cues):
        end = max(end, start + MIN_DUR)
        if n + 1 < len(cues):
            end = min(end, cues[n + 1][0] - 0.04)
        if n == 0 or out[-1][2].rstrip()[-1:] in ".?!…":
            text = text[:1].upper() + text[1:]
        out.append((start, end, text))
    return out


def write_srt(words: list[dict], dest: Path) -> Path:
    cues = build_cues(words)
    blocks = [f"{n}\n{stamp(s)} --> {stamp(e)}\n" + "\n".join(split_lines(t)) + "\n"
              for n, (s, e, t) in enumerate(cues, 1)]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(blocks), encoding="utf-8")
    return dest


def parse_srt(text: str) -> list[dict]:
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = block.strip().splitlines()
        if len(lines) < 2:
            raise ValueError(f"bloco SRT incompleto: {block!r}")
        m = re.fullmatch(r"(\S+)\s*-->\s*(\S+)", lines[1].strip())
        if not lines[0].strip().isdigit() or not m:
            raise ValueError(f"bloco SRT malformado: {block!r}")
        cues.append({"n": int(lines[0]), "start": parse_stamp(m.group(1)), "end": parse_stamp(m.group(2)),
                     "lines": lines[2:]})
    return cues


def validate(text: str, duration: float | None = None, words: list[dict] | None = None) -> dict:
    """Retorna {'falhas': [...], 'avisos': [...], 'cues': n}."""
    falhas, avisos = [], []
    try:
        cues = parse_srt(text)
    except ValueError as exc:
        return {"falhas": [str(exc)], "avisos": [], "cues": 0}
    for i, c in enumerate(cues, 1):
        label = f"legenda {c['n']}"
        if c["n"] != i:
            falhas.append(f"{label}: numeração fora de ordem (esperado {i})")
        dur = c["end"] - c["start"]
        if dur <= 0:
            falhas.append(f"{label}: duração não positiva")
            continue
        if i > 1 and c["start"] < cues[i - 2]["end"]:
            falhas.append(f"{label}: sobrepõe a anterior")
        if not c["lines"] or not any(x.strip() for x in c["lines"]):
            falhas.append(f"{label}: sem texto")
        if len(c["lines"]) > MAX_LINES:
            falhas.append(f"{label}: {len(c['lines'])} linhas (máx. {MAX_LINES})")
        for line in c["lines"]:
            if len(line) > MAX_LINE:
                falhas.append(f"{label}: linha com {len(line)} caracteres (máx. {MAX_LINE})")
        chars = len(" ".join(c["lines"]))
        cps = chars / dur
        if cps > CPS_FAIL:
            falhas.append(f"{label}: {cps:.1f} caracteres/s (máx. {CPS_FAIL})")
        elif cps > CPS_WARN:
            avisos.append(f"{label}: {cps:.1f} caracteres/s (recomendado ≤ {CPS_WARN})")
        if dur > MAX_DUR:
            avisos.append(f"{label}: {dur:.1f}s na tela (recomendado ≤ {MAX_DUR}s)")
        if duration is not None and c["end"] > duration + 0.05:
            falhas.append(f"{label}: termina depois do vídeo ({c['end']:.2f}s > {duration:.2f}s)")
    if words:
        missing = [w["w"] for w in words
                   if not any(c["start"] - 0.05 <= w["start"] and w["end"] <= c["end"] + 0.3 for c in cues)]
        if missing:
            falhas.append(f"{len(missing)} palavra(s) fora de qualquer legenda: {' '.join(missing[:8])}")
    return {"falhas": falhas, "avisos": avisos, "cues": len(cues)}


def main(argv=None):
    import argparse

    from engine.render import Episode
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--height", type=int, default=720)
    args = ap.parse_args(argv)
    ep = Episode(args.episode, args.height)
    dest = write_srt(ep.timeline.words, ep.output("srt"))
    print(dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
