"""Renderiza um episódio declarado em YAML.

    python -m engine.render episodes/<episódio> [--profile preview|entrega|teste]
                                                [--jobs N] [--no-cache] [--still T ...]

Adaptado de reformaProtestante-/pipeline/render.py (commit 4b8f111). Mudanças principais:
  * sem kit de áudio privado: trilhas comuns (narração TTS, vinheta) com loudness opcional;
  * render segmentado por cena, com cache por hash e concatenação sem recodificar;
  * transições entre cenas (crossfade, wipe, fade por cor);
  * perfis de codificação (prévia 720p rápida, entrega 1080p).

Saída em renders/<slug>/: <slug>_<altura>p.mp4, <slug>_<altura>p.srt e render_<altura>p.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

import yaml
from PIL import Image

from . import theme
from .layers import TYPES
from .layers.base import ease_in_out
from .theme import ROOT, rgb
from .timeline import Timeline

PROFILES = {
    "teste": {"height": 360, "preset": "ultrafast", "crf": 28},
    "preview": {"height": 720, "preset": "veryfast", "crf": 23},
    "entrega": {"height": 1080, "preset": "medium", "crf": 18},
}
HEIGHTS = (360, 720, 1080)
TRANSITIONS = ("crossfade", "wipe", "fade")


class Context:
    def __init__(self, timeline, height, scene_start, scene_end, pre=0.0, post=0.0):
        self.timeline, self.height = timeline, height
        self.s = height / 1080.0
        self.scene_start, self.scene_end = scene_start, scene_end
        # meia-duração das transições de entrada/saída: camadas sem `in`/`out` explícitos
        # ficam inteiras durante a mistura, em vez de sumir antes do corte
        self.pre, self.post = pre, post
        self.layers = {}

    def time(self, expr, label=""):
        return self.timeline.resolve(expr, self.scene_start, self.scene_end, label)


def _half(transition):
    if transition and transition.get("type") in ("crossfade", "wipe"):
        return float(transition.get("duration", 0.5)) / 2
    return 0.0


class Scene:
    def __init__(self, index, entry, episode, next_entry=None):
        self.index = index
        self.entry = entry
        self.start, self.end = float(entry["start"]), float(entry["end"])
        self.file = entry["file"]
        self.spec = yaml.safe_load((episode.dir / self.file).read_text(encoding="utf-8"))
        self.name = self.spec.get("name", self.file)
        self.status = self.spec.get("status", "rascunho")
        self.background = rgb(self.spec.get("background", "marinho"))
        self.fade_in = float(self.spec.get("fade_in", 0.0))
        self.fade_out = float(self.spec.get("fade_out", 0.0))
        self.static_ok = bool(self.spec.get("static_ok", False))
        self.transition = entry.get("transition")  # definida no episode.yaml, na cena que entra
        if self.transition:
            kind = self.transition.get("type")
            if kind not in TRANSITIONS:
                raise SystemExit(f"{self.file}: transição desconhecida {kind!r} (use {', '.join(TRANSITIONS)})")
        self.ctx = Context(episode.timeline, episode.height, self.start, self.end,
                           pre=_half(self.transition), post=_half((next_entry or {}).get("transition")))
        self.layers = []
        for layer_spec in self.spec.get("layers", []):
            kind = layer_spec.get("type")
            if kind not in TYPES:
                raise SystemExit(f"{self.file}: tipo de camada desconhecido {kind!r}")
            layer = TYPES[kind](layer_spec, self.ctx)
            self.layers.append(layer)
            if layer_spec.get("id"):
                self.ctx.layers[layer_spec["id"]] = layer
        self.fade_color = rgb(theme.load().get("transicao", "noite"))

    def render(self, t, size):
        frame = Image.new("RGB", size, self.background)
        for layer in self.layers:
            layer.draw(frame, t, 0)
        level = 1.0
        if self.fade_in > 0:
            level = min(level, (t - self.start) / self.fade_in + 1e-6)
        if self.fade_out > 0:
            level = min(level, (self.end - t) / self.fade_out)
        if level < 1.0:
            frame = Image.blend(Image.new("RGB", size, self.fade_color), frame, max(0.0, level))
        return frame

    def sources(self):
        out = []
        for layer in self.layers:
            out += layer.sources()
        return out


class Episode:
    def __init__(self, episode_dir, height=720):
        self.dir = Path(episode_dir).resolve()
        self.spec = yaml.safe_load((self.dir / "episode.yaml").read_text(encoding="utf-8"))
        if height not in HEIGHTS:
            raise SystemExit(f"altura {height} não suportada (use {HEIGHTS})")
        self.fps = int(self.spec.get("fps", 30))
        self.height = height
        self.size = (height * 16 // 9, height)
        self.slug = self.spec.get("slug", self.dir.name)
        self.timeline = Timeline(self.spec, self.dir)
        entries = self.spec["scenes"]
        self.scenes = [Scene(i, e, self, entries[i + 1] if i + 1 < len(entries) else None)
                       for i, e in enumerate(entries)]
        self._validate()
        self.duration = self.scenes[-1].end
        self.frames = math.ceil(self.duration * self.fps - 1e-6)
        self.out_dir = ROOT / "renders" / self.slug

    def _validate(self):
        if abs(self.scenes[0].start) > 1e-6:
            raise SystemExit("a primeira cena deve começar em 0")
        for a, b in zip(self.scenes, self.scenes[1:]):
            if abs(a.end - b.start) > 1e-6:
                raise SystemExit(f"cenas não contíguas: {a.file} termina em {a.end}, {b.file} começa em {b.start}")
            if b.transition:
                d = float(b.transition.get("duration", 0.5))
                if d / 2 > min(a.end - a.start, b.end - b.start):
                    raise SystemExit(f"transição de {d}s longa demais para {b.file}")

    # --------------------------------------------------------------- quadros
    def scene_index_at(self, t):
        for i, scene in enumerate(self.scenes):
            if scene.start <= t < scene.end:
                return i
        return len(self.scenes) - 1

    def scene_at(self, t):
        return self.scenes[self.scene_index_at(t)]

    def frame_range(self, k):
        f0 = math.ceil(self.scenes[k].start * self.fps - 1e-6)
        f1 = self.frames if k == len(self.scenes) - 1 else math.ceil(self.scenes[k].end * self.fps - 1e-6)
        return f0, f1

    def _transition_at(self, t):
        """(cena A, cena B, progresso, tipo, cor) se t estiver numa janela de transição."""
        for a, b in zip(self.scenes, self.scenes[1:]):
            if not b.transition:
                continue
            d = float(b.transition.get("duration", 0.5))
            cut = b.start
            if cut - d / 2 <= t < cut + d / 2:
                p = ease_in_out((t - (cut - d / 2)) / d)
                color = rgb(b.transition.get("color", theme.load().get("transicao", "noite")))
                return a, b, p, b.transition["type"], color
        return None

    def frame(self, index):
        t = index / self.fps
        tr = self._transition_at(t)
        if tr is None:
            return self.scene_at(t).render(t, self.size)
        a, b, p, kind, color = tr
        fa = a.render(t, self.size)
        fb = b.render(t, self.size)
        if kind == "crossfade":
            return Image.blend(fa, fb, p)
        if kind == "fade":
            solid = Image.new("RGB", self.size, color)
            return Image.blend(fa, solid, p * 2) if p < 0.5 else Image.blend(solid, fb, (p - 0.5) * 2)
        # wipe: B entra da esquerda para a direita, com borda suave
        w = self.size[0]
        edge = max(2, w // 12)
        x = p * (w + edge) - edge
        mask = Image.linear_gradient("L").rotate(270).resize((edge, self.size[1]))  # branco → preto
        full = Image.new("L", self.size, 0)
        if x > 0:
            full.paste(255, (0, 0, int(x), self.size[1]))
        full.paste(mask, (int(x), 0))
        return Image.composite(fb, fa, full)

    # ------------------------------------------------------------------ cache
    def segment_key(self, k, enc):
        h = hashlib.sha256()

        def add(obj):
            h.update(json.dumps(obj, sort_keys=True, default=str).encode())

        add({"enc": enc, "height": self.height, "fps": self.fps, "engine": engine_hash()})
        for j in (k - 1, k, k + 1):
            if 0 <= j < len(self.scenes):
                s = self.scenes[j]
                add({"j": j - k, "entry": s.entry, "spec": s.spec})
                for path in sorted(set(s.sources())):
                    add(str(path))
                    h.update(file_hash(path).encode())
        h.update(file_hash(theme.THEME_FILE).encode())
        for font, _ in theme.font_files():
            h.update(file_hash(font).encode())
        if self.spec.get("timing"):
            h.update(file_hash(self.dir / self.spec["timing"]).encode())
        return h.hexdigest()[:20]

    def output(self, suffix="mp4"):
        return self.out_dir / f"{self.slug}_{self.height}p.{suffix}"

    # ------------------------------------------------------------------- áudio
    def build_audio(self, dest: Path):
        audio = self.spec.get("audio") or {}
        tracks = audio.get("tracks", [])
        if not tracks:
            return None
        total = self.frames / self.fps
        cmd = ["ffmpeg", "-v", "error", "-y"]
        chains, labels = [], []
        for i, track in enumerate(tracks):
            path = self.dir / track["file"]
            if not path.exists():
                raise SystemExit(f"áudio ausente: {path}")
            cmd += ["-i", str(path)]
            chain = f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            if "trim_end" in track:
                chain += f"atrim=0:{track['trim_end']},asetpts=PTS-STARTPTS,"
                fade = float(track.get("fade_out", 0))
                if fade:
                    chain += f"afade=t=out:st={float(track['trim_end']) - fade}:d={fade},"
            if track.get("gain_db"):
                chain += f"volume={float(track['gain_db'])}dB,"
            delay = int(round(float(track.get("start", 0)) * 1000))
            chain += f"adelay={delay}:all=1[a{i}]"
            chains.append(chain)
            labels.append(f"[a{i}]")
        mix = (f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=longest,"
               f"apad=whole_dur={total},atrim=0:{total}")
        target = audio.get("loudnorm")
        if target:
            tp = float(audio.get("true_peak", -1.5))
            mix += f",loudnorm=I={float(target)}:TP={tp}:LRA=11,aresample=48000"
        chains.append(mix + "[out]")
        cmd += ["-filter_complex", ";".join(chains), "-map", "[out]", "-c:a", "pcm_s16le", str(dest)]
        subprocess.run(cmd, check=True)
        return dest

    # ------------------------------------------------------------------ vídeo
    def render(self, profile="preview", jobs=None, use_cache=True, log=print):
        enc = {k: v for k, v in PROFILES[profile].items() if k != "height"}
        self.out_dir.mkdir(parents=True, exist_ok=True)
        seg_dir = self.out_dir / "segmentos" / f"{self.height}p"
        seg_dir.mkdir(parents=True, exist_ok=True)
        started = time.time()
        jobs = max(1, jobs or min(os.cpu_count() or 1, len(self.scenes)))
        tasks, meta = [], []
        for k, scene in enumerate(self.scenes):
            key = self.segment_key(k, enc)
            seg = seg_dir / f"{k:02d}_{key}.mp4"
            cached = use_cache and seg.exists()
            meta.append({"scene": scene.name, "file": scene.file, "segment": seg.name, "cached": cached,
                         "frames": self.frame_range(k)[1] - self.frame_range(k)[0]})
            if not cached:
                tasks.append((str(self.dir), self.height, k, str(seg), enc, max(1, (os.cpu_count() or 1) // jobs)))
        log(f"{len(self.scenes)} cenas, {len(tasks)} a renderizar, {len(self.scenes) - len(tasks)} do cache, {jobs} processo(s)")
        if tasks:
            if jobs == 1:
                results = [_encode_segment(t) for t in tasks]
            else:
                with ProcessPoolExecutor(max_workers=jobs, mp_context=get_context("spawn")) as pool:
                    results = list(pool.map(_encode_segment, tasks))
            for k, n, secs in results:
                meta[k]["seconds"] = round(secs, 2)
                log(f"  cena {k:02d}: {n} quadros em {secs:.1f}s")
        video = self.output("video.mp4")
        listing = seg_dir / "concat.txt"
        listing.write_text("".join(f"file '{seg_dir / m['segment']}'\n" for m in meta), encoding="utf-8")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                        "-c", "copy", "-movflags", "+faststart", str(video)], check=True)
        final = self.output()
        wav = self.build_audio(self.out_dir / f"audio_{self.height}p.wav")
        if wav:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(wav), "-map", "0:v:0",
                            "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                            "-t", f"{self.frames / self.fps}", "-movflags", "+faststart", str(final)], check=True)
        else:
            shutil.copyfile(video, final)
            log("AVISO: episódio sem trilhas de áudio")
        srt = None
        if self.timeline.words:
            from subtitles.srt import write_srt
            srt = write_srt(self.timeline.words, self.output("srt"))
        info = {"episode": self.spec.get("title"), "slug": self.slug, "profile": profile, "height": self.height,
                "fps": self.fps, "frames": self.frames, "duration": self.frames / self.fps,
                "seconds": round(time.time() - started, 2), "jobs": jobs, "segments": meta,
                "output": str(final.relative_to(ROOT)), "srt": str(srt.relative_to(ROOT)) if srt else None,
                "commit": git_commit()}
        self.output("render.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"{final}  ({self.frames} quadros, {self.frames / self.fps:.3f}s, render em {info['seconds']}s)")
        return final


# ---------------------------------------------------------------- utilitários
_EPISODES = {}


def _encode_segment(task):
    ep_dir, height, k, out, enc, threads = task
    key = (ep_dir, height)
    if key not in _EPISODES:
        _EPISODES[key] = Episode(ep_dir, height)
    ep = _EPISODES[key]
    f0, f1 = ep.frame_range(k)
    w, h = ep.size
    tmp = out + ".tmp.mp4"
    started = time.time()
    ff = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
         "-r", str(ep.fps), "-i", "-", "-c:v", "libx264", "-preset", enc["preset"], "-crf", str(enc["crf"]),
         "-pix_fmt", "yuv420p", "-g", str(ep.fps * 2), "-threads", str(threads), "-an", tmp],
        stdin=subprocess.PIPE)
    try:
        for i in range(f0, f1):
            ff.stdin.write(ep.frame(i).tobytes())
    finally:
        ff.stdin.close()
    if ff.wait():
        raise SystemExit(f"ffmpeg falhou ao codificar a cena {k}")
    os.replace(tmp, out)
    return k, f1 - f0, time.time() - started


_HASHES = {}


def file_hash(path) -> str:
    path = Path(path)
    if not path.exists():
        return "ausente"
    key = (str(path), path.stat().st_mtime_ns, path.stat().st_size)
    if key not in _HASHES:
        _HASHES[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    return _HASHES[key]


def engine_hash() -> str:
    h = hashlib.sha256()
    for path in sorted((ROOT / "engine").rglob("*.py")):
        h.update(path.relative_to(ROOT).as_posix().encode())
        h.update(path.read_bytes())
    return h.hexdigest()[:16]


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Renderiza um episódio do Caderno Curioso")
    ap.add_argument("episode")
    ap.add_argument("--profile", default="preview", choices=list(PROFILES))
    ap.add_argument("--height", type=int, choices=HEIGHTS, help="sobrepõe a altura do perfil")
    ap.add_argument("--jobs", type=int, help="processos paralelos (padrão: núcleos disponíveis)")
    ap.add_argument("--no-cache", action="store_true", help="ignora segmentos já renderizados")
    ap.add_argument("--still", type=float, action="append", help="salva um PNG no tempo t (s) e sai")
    args = ap.parse_args(argv)
    height = args.height or PROFILES[args.profile]["height"]
    ep = Episode(args.episode, height)
    if args.still:
        ep.out_dir.mkdir(parents=True, exist_ok=True)
        for t in args.still:
            path = ep.out_dir / f"still_{height}p_{t:07.3f}.png"
            ep.frame(int(round(t * ep.fps))).save(path)
            print(path)
        return 0
    ep.render(args.profile, args.jobs, not args.no_cache)
    return 0


if __name__ == "__main__":
    sys.exit(main())
