"""Medições sobre arquivos de mídia via ffprobe/ffmpeg (sem dependências extras).

Partes adaptadas de reformaProtestante-/pipeline/qa.py (commit 4b8f111).
"""
from __future__ import annotations

import json
import re
import struct
import subprocess

import numpy as np


def probe(path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                         capture_output=True, check=True, text=True).stdout
    return json.loads(out)


def faststart(path) -> bool:
    """True se o átomo 'moov' vem antes do 'mdat' (reprodução imediata na web)."""
    with open(path, "rb") as f:
        while True:
            head = f.read(8)
            if len(head) < 8:
                return False
            size, kind = struct.unpack(">I4s", head)
            if kind == b"moov":
                return True
            if kind == b"mdat":
                return False
            if size == 1:
                size = struct.unpack(">Q", f.read(8))[0] - 8
            f.seek(size - 8, 1)


def gray_frames(path, width=160, height=90) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0", "-vf", f"scale={width}:{height}",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, height * width)


def pcm(path, rate=16000, channels=1, start=None, duration=None) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error"]
    if start is not None:
        cmd += ["-ss", f"{start}"]
    if duration is not None:
        cmd += ["-t", f"{duration}"]
    cmd += ["-i", str(path), "-vn", "-ac", str(channels), "-ar", str(rate), "-f", "f32le", "-"]
    data = np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, dtype=np.float32)
    return data.reshape(-1, channels) if channels > 1 else data


def ebur128(path) -> dict:
    """Loudness integrada (LUFS), faixa (LU) e pico real (dBTP) segundo EBU R128."""
    err = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-map", "0:a:0", "-filter_complex",
                          "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    summary = err[err.rfind("Summary:"):]

    def grab(label):
        m = re.search(label + r":\s+(-?[\d.]+|-inf)", summary)
        return float(m.group(1)) if m and m.group(1) != "-inf" else float("-inf")
    return {"I": grab("I"), "LRA": grab("LRA"), "TP": grab("Peak")}


def silences(path, noise_db=-45, min_dur=0.6) -> list[tuple[float, float]]:
    err = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-map", "0:a:0", "-af",
                          f"silencedetect=noise={noise_db}dB:d={min_dur}", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", err)]
    out = []
    for i, s in enumerate(starts):
        out.append((max(0.0, s), ends[i] if i < len(ends) else float("inf")))
    return out


def extract_frame(video, t, dest):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                    "-q:v", "3", str(dest)], check=True)


def luminance(c):
    def lin(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2])


def contrast(c1, c2):
    a, b = sorted((luminance(c1), luminance(c2)), reverse=True)
    return (a + 0.05) / (b + 0.05)
