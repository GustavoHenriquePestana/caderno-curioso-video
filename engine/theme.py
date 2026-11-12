"""Tema visual: cores nomeadas e fontes por papel, lidos de brand/theme.yaml."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from PIL import ImageFont

ROOT = Path(__file__).resolve().parents[1]
THEME_FILE = ROOT / "brand" / "theme.yaml"


@lru_cache(maxsize=4)
def load(path: str | None = None) -> dict:
    p = Path(path) if path else THEME_FILE
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def rgb(color, theme: dict | None = None) -> tuple:
    """Aceita nome de cor do tema, '#RRGGBB' ou lista [r, g, b]."""
    if isinstance(color, (list, tuple)):
        return tuple(int(c) for c in color[:3])
    color = str(color).strip()
    named = (theme or load())["cores"]
    if color in named:
        color = named[color]
    if not color.startswith("#") or len(color) != 7:
        raise ValueError(f"cor inválida: {color!r} (use um nome do tema ou #RRGGBB)")
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def font_path(role: str, style: str | None = None) -> tuple[Path, int]:
    """Resolve um papel (titulo, texto, sans…) ou família para (arquivo, peso padrão)."""
    theme = load()
    fonts = theme["fontes"]
    papel = fonts["papeis"].get(role)
    if papel:
        family, st, weight = papel["familia"], papel.get("estilo", "regular"), papel.get("peso", 400)
    else:
        family, st, weight = role, "regular", 400
    if family == "serifada":
        family = fonts["serifada"]
    if family not in fonts["familias"]:
        raise ValueError(f"fonte/papel desconhecido: {role!r}")
    st = style or st
    return ROOT / fonts["familias"][family][st], int(weight)


@lru_cache(maxsize=256)
def _font(path: str, size: int, weight: int) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(path, size)
    try:
        axes = f.get_variation_axes()
    except OSError:  # fonte estática
        return f
    values = []
    for axis in axes:
        name = axis["name"]
        name = name.decode() if isinstance(name, bytes) else str(name)
        lo, hi, default = axis["minimum"], axis["maximum"], axis["default"]
        if name.lower().startswith("weight"):
            values.append(max(lo, min(hi, weight)))
        elif name.lower().startswith("optical"):
            values.append(max(lo, min(hi, round(size * 0.75))))  # px → pt aproximado
        else:
            values.append(default)
    f.set_variation_by_axes(values)
    return f


def font(role: str, size: int, weight: int | None = None, style: str | None = None) -> ImageFont.FreeTypeFont:
    path, default_weight = font_path(role, style)
    return _font(str(path), int(size), int(weight if weight is not None else default_weight))


def font_files() -> list[tuple[Path, Path]]:
    """(arquivo da fonte, arquivo de licença) de todas as famílias declaradas."""
    out = []
    for fam in load()["fontes"]["familias"].values():
        for key in ("regular", "italico"):
            if key in fam:
                out.append((ROOT / fam[key], ROOT / fam["licenca"]))
    return out
