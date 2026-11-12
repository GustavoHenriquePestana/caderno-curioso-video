"""Tipografia editorial. Adaptado de reformaProtestante-/pipeline/layers.py (classe Text).

Campos: text, pos [x, y] (1920x1080), anchor (lt, mm, rb…), font (papel do tema), size,
weight, color, align (left|center|right), max_width, leading, tracking (fração do corpo),
upper, bg {color, alpha, outline, outline_width, radius}, pad [x, y], shadow, role (credit).
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

from .. import theme
from .base import SpriteLayer, rgb, supersampled


class Text(SpriteLayer):
    def build(self):
        sp, s = self.spec, self.ctx.s
        size = max(8, round(float(sp.get("size", 56)) * s))
        f = theme.font(sp.get("font", "texto"), size, sp.get("weight"))
        self.font, self.tracking = f, float(sp.get("tracking", 0)) * size
        text = str(sp["text"])
        if sp.get("upper"):
            text = text.upper()
        lines = self._wrap(text, f, sp.get("max_width"))
        ascent, descent = f.getmetrics()
        line_h = ascent + descent
        spacing = round(size * float(sp.get("leading", 0.22)))
        widths = [self._width(line) for line in lines]
        tw = math.ceil(max(widths)) if widths else 1
        th = len(lines) * line_h + (len(lines) - 1) * spacing
        color = rgb(sp.get("color", "creme"))
        align = sp.get("align", "left")
        bg = sp.get("bg")
        default_pad = [40, 20] if bg else [0, 0]
        pad_x, pad_y = (round(v * s) for v in sp.get("pad", default_pad))
        margin = round(8 * s) + 2
        w, h = tw + 2 * pad_x + 2 * margin, th + 2 * pad_y + 2 * margin
        sprite = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        if bg:
            fill = rgb(bg.get("color", "noite")) + (int(255 * float(bg.get("alpha", 0.9))),)
            outline = rgb(bg["outline"]) + (255,) if bg.get("outline") else None
            radius = round(bg.get("radius", 10) * s)
            lw = max(1, round(bg.get("outline_width", 3) * s))
            pw, ph = w - 2 * margin, h - 2 * margin
            panel = supersampled((pw, ph), lambda d, m: d.rounded_rectangle(
                (m, m, pw * m - m, ph * m - m), radius * m, fill=fill, outline=outline,
                width=lw * m if outline else 0))
            sprite.alpha_composite(panel, (margin, margin))
        d = ImageDraw.Draw(sprite)
        tx, ty = margin + pad_x, margin + pad_y
        if sp.get("shadow", False):
            off = max(1, round(3 * s))
            self._draw_lines(d, lines, widths, tw, tx + off, ty + off, line_h, spacing, align,
                             rgb(sp.get("shadow_color", "noite")) + (200,))
        self._draw_lines(d, lines, widths, tw, tx, ty, line_h, spacing, align, color + (255,))
        ax, ay = sp.get("anchor", "lt")
        px, py = float(sp["pos"][0]) * s, float(sp["pos"][1]) * s
        ox = px - {"l": 0, "m": w / 2, "r": w}[ax]
        oy = py - {"t": 0, "m": h / 2, "b": h}[ay]
        self.font_px, self.color, self.lines = size, color, lines
        # caixa do texto (métrica tipográfica, sem o espaço vazio acima das maiúsculas)
        top = round(ascent * 0.15)
        self.text_box = (ox + tx, oy + ty + top, ox + tx + tw, oy + ty + th - round(descent * 0.4))
        self.backed = bool(bg)
        return sprite, (round(ox), round(oy))

    # ------------------------------------------------------------------ layout
    def _width(self, line: str) -> float:
        if not self.tracking:
            return self.font.getlength(line)
        return sum(self.font.getlength(c) for c in line) + self.tracking * max(0, len(line) - 1)

    def _draw_lines(self, d, lines, widths, tw, x0, y0, line_h, spacing, align, fill):
        for i, (line, lw) in enumerate(zip(lines, widths)):
            x = x0 + {"left": 0, "center": (tw - lw) / 2, "right": tw - lw}[align]
            y = y0 + i * (line_h + spacing)
            if not self.tracking:
                d.text((x, y), line, font=self.font, fill=fill)
                continue
            for c in line:
                d.text((x, y), c, font=self.font, fill=fill)
                x += self.font.getlength(c) + self.tracking

    def _wrap(self, text, f, max_width):
        if not max_width:
            return text.split("\n")
        limit = float(max_width) * self.ctx.s
        out = []
        for para in text.split("\n"):
            line = ""
            for word in para.split():
                trial = f"{line} {word}".strip()
                if self._width(trial) <= limit or not line:
                    line = trial
                else:
                    out.append(line)
                    line = word
            out.append(line)
        return out
