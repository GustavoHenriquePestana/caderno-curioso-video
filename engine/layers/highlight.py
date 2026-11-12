"""Moldura ou sublinhado que se desenha progressivamente.

Adaptado de reformaProtestante-/pipeline/layers.py (classe Highlight).
Campos: rect [x, y, w, h] ou over (id de picture) + frac [x0, y0, x1, y1]; style box|underline;
draw (s); color; width; pace linear|ease.
"""
from __future__ import annotations

from PIL import ImageDraw

from .base import Layer, ease, rgb


class Highlight(Layer):
    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        self.draw_time = float(spec.get("draw", 0.6))
        s = ctx.s
        if spec.get("over"):
            bx0, by0, bx1, by1 = ctx.layers[spec["over"]].image_box
            fx0, fy0, fx1, fy1 = spec["frac"]
            self.rect = (bx0 + fx0 * (bx1 - bx0), by0 + fy0 * (by1 - by0),
                         (fx1 - fx0) * (bx1 - bx0), (fy1 - fy0) * (by1 - by0))
        else:
            self.rect = tuple(float(v) * s for v in spec["rect"])

    def draw(self, frame, t, frame_index):
        st = self.state(t)
        if st is None:
            return
        s = self.ctx.s
        x, y, w, h = self.rect
        color = rgb(self.spec.get("color", "ouro"))
        lw = max(2, round(float(self.spec.get("width", 6)) * s))
        p = (t - self.t_in) / self.draw_time if self.draw_time > 0 else 1.0
        p = min(1.0, max(0.0, p)) if self.spec.get("pace") == "linear" else ease(p)
        p *= 1 if st[0] > 0.5 else st[0] * 2
        d = ImageDraw.Draw(frame)
        if self.spec.get("style", "box") == "underline":
            if p > 0:
                d.line((x, y + h, x + w * p, y + h), fill=color, width=lw)
            return
        path = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
        done = 2 * (w + h) * p
        for (ax, ay), (bx, by) in zip(path, path[1:]):
            seg = abs(bx - ax) + abs(by - ay)
            if done <= 0:
                break
            f = min(1.0, done / seg)
            d.line((ax, ay, ax + (bx - ax) * f, ay + (by - ay) * f), fill=color, width=lw)
            done -= seg
