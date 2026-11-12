"""Selo do Caderno Curioso redesenhado em vetor (procedural), com animação de entrada.

Proporções medidas na logo enviada pelo autor (1254x1254 px, raio externo 326 px).
Textos do anel corrigidos: "TECNOLOGIA" (o original dizia "TECNOLOGA").
Campos: pos [x, y] (centro), radius (raio externo, unidades 1920x1080), draw (s da
animação das órbitas; 0 = estático), top, bottom (textos do anel), colors.
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

from .. import theme
from .base import Layer, ease, rgb, with_opacity

# frações do raio externo
OUTER_RING_R, OUTER_RING_W = 0.978, 0.018
THIN_RING_R, THIN_RING_W = 0.945, 0.005
DISC_R = 0.721
TEXT_R, CAP_H = 0.832, 0.092
ORBIT_A, ORBIT_B, ORBIT_W = 0.49, 0.17, 0.016
NUCLEUS_R = 0.083
RECT_R, RECT_W, RECT_H = 0.92, 0.058, 0.12
DOT_R = 0.013
SPAN_TOP, SPAN_BOTTOM = 134, 156   # graus ocupados pelos textos do anel (medidos)


class Logo(Layer):
    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        s = ctx.s
        self.R = float(spec.get("radius", 300)) * s
        self.cx, self.cy = (float(v) * s for v in spec.get("pos", [960, 540]))
        self.draw_time = float(spec.get("draw", 1.4))
        self.c_navy = rgb(spec.get("navy", "marinho"))
        self.c_gold = rgb(spec.get("gold", "ouro"))
        self.c_ochre = rgb(spec.get("ochre", "ocre"))
        self.c_bg = rgb(spec.get("paper", "creme"))
        self.top = spec.get("top", "CIÊNCIA • TECNOLOGIA")
        self.bottom = spec.get("bottom", "BOAS NOTÍCIAS • DESCOBERTAS")
        half = math.ceil(self.R * 1.03)
        self.half = half
        self.base = self._base(3)
        self.full = self._with_atom(self.base.copy(), 1.0, 3)

    # ------------------------------------------------------------- desenho
    def _canvas(self, m):
        return Image.new("RGBA", (2 * self.half * m, 2 * self.half * m), (0, 0, 0, 0))

    def _base(self, m):
        R, c = self.R * m, self.half * m
        img = self._canvas(m)
        d = ImageDraw.Draw(img)
        r = R * OUTER_RING_R
        d.ellipse((c - R, c - R, c + R, c + R), fill=self.c_bg + (255,))
        d.ellipse((c - r, c - r, c + r, c + r), outline=self.c_navy + (255,), width=max(1, round(R * OUTER_RING_W)))
        r = R * THIN_RING_R
        d.ellipse((c - r, c - r, c + r, c + r), outline=self.c_navy + (255,), width=max(1, round(R * THIN_RING_W)))
        r = R * DISC_R
        d.ellipse((c - r, c - r, c + r, c + r), fill=self.c_navy + (255,))
        for side in (-1, 1):  # retângulos laterais (ocre, só contorno)
            x = c + side * R * RECT_R
            w, h = R * RECT_W / 2, R * RECT_H / 2
            d.rectangle((x - w, c - h, x + w, c + h), fill=self.c_bg + (255,), outline=self.c_ochre + (255,),
                        width=max(1, round(R * 0.006)))
            d.line((x, c - h, x, c + h), fill=self.c_ochre + (255,), width=max(1, round(R * 0.004)))
        self._arc_text(img, self.top, m, top=True)
        self._arc_text(img, self.bottom, m, top=False)
        return img.resize((2 * self.half, 2 * self.half), Image.LANCZOS)

    def _arc_text(self, img, text, m, top):
        R, c = self.R * m, self.half * m
        rt = R * TEXT_R
        f = theme.font(self.spec.get("ring_font", "titulo"), max(6, round(R * CAP_H / 0.68)),
                       self.spec.get("ring_weight", 500))
        cap = f.getbbox("H")[3] - f.getbbox("H")[1]
        chars = list(text)
        widths = [f.getlength(ch) if ch != "•" else R * DOT_R * 6 for ch in chars]
        span = math.radians(float(self.spec.get("span_top" if top else "span_bottom",
                                                SPAN_TOP if top else SPAN_BOTTOM)))
        extra = (rt * span - sum(widths)) / max(1, len(chars) - 1)
        pos = 0.0
        for ch, w in zip(chars, widths):
            centre = pos + w / 2
            pos += w + extra
            if ch == " ":
                continue
            phi = -span / 2 + centre / rt if top else math.pi + span / 2 - centre / rt
            x, y = c + rt * math.sin(phi), c - rt * math.cos(phi)
            if ch == "•":
                r = R * DOT_R
                ImageDraw.Draw(img).ellipse((x - r, y - r, x + r, y + r), fill=self.c_ochre + (255,))
                continue
            size = round(cap * 3)
            glyph = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            ImageDraw.Draw(glyph).text((size / 2, size / 2 + cap / 2), ch, font=f, fill=self.c_navy + (255,), anchor="ms")
            angle = -math.degrees(phi) if top else 180 - math.degrees(phi)
            glyph = glyph.rotate(angle, resample=Image.BICUBIC)
            img.alpha_composite(glyph, (round(x - size / 2), round(y - size / 2)))

    def _with_atom(self, img, p, m):
        """Desenha órbitas (progresso p em 0..1) e núcleo sobre `img` (tamanho final)."""
        big = self._canvas(m)
        d = ImageDraw.Draw(big)
        R, c = self.R * m, self.half * m
        lw = max(1, round(R * ORBIT_W))
        for k, rot in enumerate((0, 60, -60)):
            q = min(1.0, max(0.0, (p * 1.25 - k * 0.12)))
            q = ease(q)
            if q <= 0:
                continue
            n = 160
            pts = []
            for i in range(int(n * q) + 1):
                u = math.tau * i / n + math.pi
                ex, ey = R * ORBIT_A * math.cos(u), R * ORBIT_B * math.sin(u)
                a = math.radians(rot)
                pts.append((c + ex * math.cos(a) - ey * math.sin(a), c + ex * math.sin(a) + ey * math.cos(a)))
            if len(pts) > 1:
                d.line(pts, fill=self.c_gold + (255,), width=lw, joint="curve")
        grow = ease((p - 0.55) / 0.45)
        if grow > 0:
            r = R * NUCLEUS_R * (grow + 0.12 * math.sin(math.pi * grow))
            d.ellipse((c - r, c - r, c + r, c + r), fill=self.c_gold + (255,))
        small = big.resize(img.size, Image.LANCZOS)
        img.alpha_composite(small)
        return img

    def draw(self, frame, t, frame_index):
        st = self.state(t)
        if st is None:
            return
        opacity, (dx, dy) = st
        p = 1.0 if self.draw_time <= 0 else (t - self.t_in) / self.draw_time
        sprite = self.full if p >= 1 else self._with_atom(self.base.copy(), max(0.0, p), 2)
        sprite = with_opacity(sprite, opacity)
        s = self.ctx.s
        pos = (round(self.cx - self.half + dx * s), round(self.cy - self.half + dy * s))
        frame.paste(sprite, pos, sprite)
