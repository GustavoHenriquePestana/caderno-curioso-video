"""Marca os tempos de cada palavra de uma narração (dependência opcional: faster-whisper).

Adaptado de reformaProtestante-/pipeline/transcribe.py (commit 4b8f111).

    pip install -r requirements-align.txt
    python -m align.transcribe narracao=caminho/narracao.wav saida.json [--model small] \
        [--roteiro narracao=episodes/x/roteiro.md]

Com --roteiro, o texto das palavras vem do roteiro (align.reconcile) e só os tempos vêm
do reconhecimento de fala — assim as legendas reproduzem o roteiro aprovado.
"""
from __future__ import annotations

import argparse
import json
import subprocess

import numpy as np


def load(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("pairs", nargs="+", help="chave=arquivo ... saida.json")
    ap.add_argument("--model", default="small", help="tiny|base|small|medium (CPU, int8)")
    ap.add_argument("--roteiro", action="append", default=[], help="chave=roteiro.md")
    args = ap.parse_args(argv)
    *pairs, dest = args.pairs
    from faster_whisper import WhisperModel  # import tardio: dependência opcional

    from .reconcile import reconcile, script_words
    scripts = dict(p.split("=", 1) for p in args.roteiro)
    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    out = {}
    for pair in pairs:
        key, path = pair.split("=", 1)
        segments, _ = model.transcribe(load(path), language="pt", word_timestamps=True, beam_size=5)
        asr = [{"w": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)}
               for s in segments for w in s.words]
        if key in scripts:
            with open(scripts[key], encoding="utf-8") as f:
                asr, report = reconcile(script_words(f.read()), asr)
            print(key, "reconciliação:", report)
        out[key] = asr
        print(key, " ".join(w["w"] for w in out[key]))
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=0)


if __name__ == "__main__":
    main()
