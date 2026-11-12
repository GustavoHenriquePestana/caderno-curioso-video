"""Baixa o contorno de terras do Natural Earth (domínio público) e grava em formato compacto.

    python scripts/fetch_geodata.py [--scale 110m]

Resultado: assets/geo/ne_<escala>_land.json ({"source", "sha256_origem", "rings"}).
Registre/atualize assets/geo/PROVENANCE.yaml ao trocar a escala.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_{scale}_land.geojson"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", default="110m", choices=["110m", "50m"])
    args = ap.parse_args(argv)
    url = URL.format(scale=args.scale)
    raw = urllib.request.urlopen(url, timeout=60).read()
    geo = json.loads(raw)
    rings = []
    for feat in geo["features"]:
        g = feat["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        for poly in polys:
            rings.append([[round(x, 3), round(y, 3)] for x, y in poly[0]])
    out = {"source": f"Natural Earth {args.scale} land (domínio público)", "url": url,
           "sha256_origem": hashlib.sha256(raw).hexdigest(), "rings": rings}
    dest = ROOT / "assets" / "geo" / f"ne_{args.scale}_land.json"
    dest.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(dest, len(rings), "anéis", dest.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
