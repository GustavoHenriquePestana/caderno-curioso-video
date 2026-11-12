"""Folha de comparação das fontes serifadas candidatas (para escolha do autor).

    python scripts/font_specimen.py [saida.jpg]

Também confere se cada fonte tem os glifos usados em textos científicos em português.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import theme  # noqa: E402

CANDIDATAS = ["libre_caslon", "source_serif", "crimson_pro"]
GLIFOS = "ãõçéêíóôúàÃÕÇÉÊÍÓÔÚÀ·—–−°µ₂³±×≈→←…“”"
TITULO = "O gelo que guarda o ar de outra época"
CORPO = ("Num ponto da Antártida Oriental, pesquisadores retiraram um cilindro de gelo "
         "com 2,8 km de comprimento. As bolhas presas nele são amostras de atmosfera antiga.")
NUMEROS = "1,2 milhão de anos · 2.800 m · −35 °C · CO₂ · 41 mil → 100 mil anos"


def has_glyph(f: ImageFont.FreeTypeFont, ch: str) -> bool:
    def raster(text):
        m = f.getmask(text)
        return m.size, bytes(m)
    return raster(ch) != raster(chr(0xFFFF))  # compara com o glifo .notdef


def font_for(family, style, size, weight):
    fam = theme.load()["fontes"]["familias"][family]
    return theme._font(str(ROOT / fam[style]), size, weight)


def main(dest=None):
    dest = Path(dest or ROOT / "renders" / "especime_fontes.jpg")
    W, col_h = 1920, 620
    sheet = Image.new("RGB", (W, col_h * len(CANDIDATAS) + 60), theme.rgb("creme"))
    d = ImageDraw.Draw(sheet)
    navy, ochre = theme.rgb("marinho"), theme.rgb("ocre")
    sans = theme.font("sans", 26)
    d.text((40, 16), "Candidatas serifadas (SIL OFL 1.1) — números e legendas em Source Sans 3", font=sans, fill=navy)
    report = {}
    for i, fam in enumerate(CANDIDATAS):
        y = 60 + i * col_h
        d.line((40, y, W - 40, y), fill=ochre, width=2)
        reg = font_for(fam, "regular", 40, 400)
        missing = [c for c in GLIFOS if not has_glyph(reg, c)]
        report[fam] = missing
        d.text((40, y + 14), f"{fam}  ·  glifos ausentes: {''.join(missing) or 'nenhum'}", font=sans, fill=ochre)
        caps = font_for(fam, "regular", 110, 600)
        x = 40
        for c in "CADERNO":
            d.text((x, y + 60), c, font=caps, fill=navy)
            x += caps.getlength(c) + 110 * 0.14
        ital = font_for(fam, "italico", 100, 500)
        d.text((x + 40, y + 66), "curioso", font=ital, fill=navy)
        d.text((40, y + 210), TITULO, font=font_for(fam, "regular", 72, 600), fill=navy)
        body = font_for(fam, "regular", 44, 400)
        words, line, yy = CORPO.split(), "", y + 310
        for w in words:
            trial = f"{line} {w}".strip()
            if body.getlength(trial) > W - 80:
                d.text((40, yy), line, font=body, fill=navy)
                line, yy = w, yy + 58
            else:
                line = trial
        d.text((40, yy), line, font=body, fill=navy)
        d.text((40, yy + 74), NUMEROS, font=font_for(fam, "regular", 44, 400), fill=navy)
        d.text((40, yy + 140), NUMEROS + "   ← Source Sans 3", font=theme.font("numeros", 40), fill=ochre)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest, quality=90)
    print(dest)
    for fam, missing in report.items():
        print(f"{fam}: glifos ausentes = {''.join(missing) or 'nenhum'}")
    print("source_sans: glifos ausentes =",
          "".join(c for c in GLIFOS if not has_glyph(theme.font("sans", 40), c)) or "nenhum")


if __name__ == "__main__":
    main(*sys.argv[1:])
