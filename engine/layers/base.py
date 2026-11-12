"""Base das camadas. Adaptado de reformaProtestante-/pipeline/layers.py (commit 4b8f111).

Todas as camadas usam coordenadas de projeto 1920x1080 e desenham direto na resolução de
saída (fator `ctx.s`). Tempos `in`/`out` aceitam as expressões de engine.timeline.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw

from .. import theme
from ..theme import ROOT


def ease(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def ease_in_out(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 3 * x * x - 2 * x * x * x


def rgb(color) -> tuple:
    return theme.rgb(color)


@lru_cache(maxsize=64)
def load_rgba(path: str) -> Image.Image:
    return Image.open(ROOT / path).convert("RGBA")


def with_opacity(sprite: Image.Image, opacity: float) -> Image.Image:
    if opacity >= 0.999:
        return sprite
    out = sprite.copy()
    out.putalpha(sprite.getchannel("A").point(lambda a: int(a * opacity)))
    return out


def supersampled(size, painter, factor: int = 3) -> Image.Image:
    """Desenha em resolução maior e reduz, para bordas suaves em gráficos vetoriais."""
    big = Image.new("RGBA", (max(1, size[0]) * factor, max(1, size[1]) * factor), (0, 0, 0, 0))
    painter(ImageDraw.Draw(big), factor)
    return big.resize((max(1, size[0]), max(1, size[1])), Image.LANCZOS)


class Layer:
    #: True quando o conteúdo depende só de opacidade/deslize (útil para cache e QA)
    sprite_based = False

    def __init__(self, spec: dict, ctx):
        self.spec, self.ctx = spec, ctx
        self.enabled = True
        self.name = str(spec.get("id") or spec.get("text") or spec.get("file") or spec["type"])
        self.t_in = ctx.time(spec.get("in", "start"), self.name)
        self.t_out = ctx.time(spec.get("out", "end"), self.name)
        self.fade = float(spec.get("fade", 0.35))
        self.fade_out = float(spec.get("fade_out", self.fade))
        if "in" not in spec and getattr(ctx, "pre", 0):      # cena entra por transição
            self.t_in = ctx.scene_start - ctx.pre
            self.fade = float(spec.get("fade", 0.0))
        if "out" not in spec and getattr(ctx, "post", 0):    # cena sai por transição
            self.t_out = ctx.scene_end + ctx.post
            self.fade_out = float(spec.get("fade_out", 0.0))
        self.slide = spec.get("slide", [0, 0])

    def state(self, t: float):
        """(opacidade, deslocamento em unidades de projeto) ou None se invisível."""
        if not self.enabled or t < self.t_in or t >= self.t_out:
            return None
        a_in = ease((t - self.t_in) / self.fade) if self.fade > 0 else 1.0
        a_out = ease((self.t_out - t) / self.fade_out) if self.fade_out > 0 else 1.0
        k = 1 - a_in
        return min(a_in, a_out), (self.slide[0] * k, self.slide[1] * k)

    def draw(self, frame: Image.Image, t: float, frame_index: int) -> None:
        raise NotImplementedError

    def sources(self) -> list[Path]:
        """Arquivos externos de que a camada depende (cache e verificação de direitos)."""
        return []


class SpriteLayer(Layer):
    """Camada cujo conteúdo é uma imagem fixa com opacidade/deslize animados."""
    sprite_based = True

    def build(self) -> tuple[Image.Image, tuple[float, float]]:
        raise NotImplementedError

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        self.sprite, self.origin = self.build()  # origin em pixels de saída

    def draw(self, frame, t, frame_index):
        st = self.state(t)
        if st is None:
            return
        opacity, (dx, dy) = st
        s = self.ctx.s
        pos = (round(self.origin[0] + dx * s), round(self.origin[1] + dy * s))
        sprite = with_opacity(self.sprite, opacity)
        frame.paste(sprite, pos, sprite)

    def bbox(self):
        return (self.origin[0], self.origin[1],
                self.origin[0] + self.sprite.width, self.origin[1] + self.sprite.height)


class Fill(Layer):
    """Preenche o quadro com uma cor (opcionalmente translúcida) — véus e fundos."""

    def draw(self, frame, t, frame_index):
        st = self.state(t)
        if st is None:
            return
        color = rgb(self.spec["color"])
        alpha = float(self.spec.get("alpha", 1.0)) * st[0]
        if alpha >= 0.999:
            frame.paste(color, (0, 0, frame.width, frame.height))
        else:
            frame.paste(Image.blend(frame, Image.new("RGB", frame.size, color), alpha))
