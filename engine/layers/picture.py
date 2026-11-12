"""Imagem documental numa caixa fixa, com crédito e rótulo de ilustração.

Adaptado de reformaProtestante-/pipeline/layers.py (classe Picture). Novidades:
  * exige registro em PROVENANCE.yaml (verificado pelo QA de direitos);
  * `credit: true` escreve o crédito do registro sob a imagem;
  * imagens com `natureza: ilustrativa` recebem o rótulo "Ilustração" (desligável só com
    `rotulo: false`, o que o QA aponta como falha).
"""
from __future__ import annotations

from PIL import Image, ImageDraw

from .. import provenance, theme
from ..theme import ROOT
from .base import SpriteLayer, load_rgba, rgb


class Picture(SpriteLayer):
    def build(self):
        sp, s = self.spec, self.ctx.s
        self.path = ROOT / sp["file"]
        self.record = provenance.record_for(self.path)
        img = load_rgba(sp["file"])
        self.native_size = img.size
        if sp.get("crop"):
            x0, y0, x1, y1 = sp["crop"]
            img = img.crop((round(x0 * img.width), round(y0 * img.height),
                            round(x1 * img.width), round(y1 * img.height)))
        bx, by, bw, bh = (float(v) * s for v in sp["box"])
        scale = min(bw / img.width, bh / img.height)
        self.upscale = scale
        size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
        img = img.resize(size, Image.LANCZOS)
        border = round(float(sp.get("border", 0)) * s)
        credit_text = self._credit_text()
        cfont = theme.font("credito", max(8, round(26 * s))) if credit_text else None
        credit_h = round(cfont.getmetrics()[0] + cfont.getmetrics()[1] + 10 * s) if cfont else 0
        w, h = size[0] + 2 * border, size[1] + 2 * border + credit_h
        sprite = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(sprite)
        if border:
            d.rectangle((0, 0, w - 1, size[1] + 2 * border - 1), fill=rgb(sp.get("border_color", "creme")) + (255,))
        sprite.paste(img, (border, border), img)
        self.label = None
        if self._needs_label():
            self.label = str(sp.get("rotulo_texto", "Ilustração"))
            lf = theme.font("sans_forte", max(8, round(24 * s)))
            pad = round(8 * s)
            tw = lf.getlength(self.label)
            asc, desc = lf.getmetrics()
            d.rectangle((border + pad, border + pad, border + pad * 3 + tw, border + pad * 2 + asc + desc),
                        fill=rgb("noite") + (220,))
            d.text((border + pad * 2, border + pad * 1.5), self.label, font=lf, fill=rgb("creme") + (255,))
        if credit_text:
            d.text((w, size[1] + 2 * border + round(6 * s)), credit_text, font=cfont,
                   fill=rgb(sp.get("credit_color", "creme")) + (255,), anchor="ra")
        self.credit_shown = bool(credit_text)
        ox = bx + (bw - size[0]) / 2 - border
        oy = by + (bh - size[1]) / 2 - border
        self.image_box = (ox + border, oy + border, ox + border + size[0], oy + border + size[1])
        return sprite, (round(ox), round(oy))

    def _credit_text(self):
        if not self.spec.get("credit"):
            return None
        return (self.record or {}).get("credito") or "CRÉDITO AUSENTE"

    def _needs_label(self):
        rotulo = self.spec.get("rotulo")
        if rotulo is False:
            return False
        return rotulo is True or (self.record or {}).get("natureza") == "ilustrativa"

    def sources(self):
        return [self.path, self.path.parent / "PROVENANCE.yaml"]
