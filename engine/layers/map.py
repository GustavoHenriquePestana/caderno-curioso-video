"""Mapa estilizado (projeção equiretangular corrigida pela latitude média).

Adaptado de reformaProtestante-/pipeline/layers.py (classe Map). Aceita GeoJSON
(FeatureCollection de Polygon/MultiPolygon) ou o formato compacto {"rings": [...]}.
Campos: geojson, box [x, y, w, h], bbox [lon0, lat0, lon1, lat1], sea, land, coast, grid,
points [{at, label, label_offset, color, radius}], rings [{at, in, radius, period, count}],
routes [{from, to, in, draw, bend, label}], dim, dim_at, credit (texto ou true).
Atenção: perto dos polos a projeção distorce muito — use outro recurso para a Antártida.
"""
from __future__ import annotations

import json
import math

from PIL import Image, ImageDraw

from .. import theme
from ..theme import ROOT
from .base import Layer, ease, rgb, supersampled


def load_rings(path) -> list:
    geo = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if "rings" in geo:
        return geo["rings"]
    rings = []
    for feat in geo.get("features", []):
        g = feat.get("geometry") or {}
        polys = [g["coordinates"]] if g.get("type") == "Polygon" else g.get("coordinates", []) if g.get("type") == "MultiPolygon" else []
        for poly in polys:
            rings.extend(poly[:1])  # só o contorno externo
    return rings


class Map(Layer):
    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        s = ctx.s
        self.box = [float(v) * s for v in spec["box"]]
        lon0, lat0, lon1, lat1 = spec["bbox"]
        self.kx = math.cos(math.radians((lat0 + lat1) / 2))
        sx = self.box[2] / ((lon1 - lon0) * self.kx)
        sy = self.box[3] / (lat1 - lat0)
        self.scale = max(sx, sy)  # cobre a caixa inteira
        self.cx, self.cy = (lon0 + lon1) / 2, (lat0 + lat1) / 2
        self.base = self._land(spec)
        self.points = spec.get("points", [])
        self.rings = [dict(r, t0=ctx.time(r["in"], "onda")) for r in spec.get("rings", [])]
        self.routes = [dict(r, t0=ctx.time(r["in"], f"rota {r.get('label', '')}")) for r in spec.get("routes", [])]
        self.label_font = theme.font("sans_forte", max(8, round(float(spec.get("label_size", 40)) * s)))
        self.t_dim = ctx.time(spec["dim_at"], "") if spec.get("dim_at") is not None else None
        credit = spec.get("credit")
        self.credit = "Dados: Natural Earth (domínio público)" if credit is True else credit

    def project(self, lon, lat):
        x = self.box[2] / 2 + (lon - self.cx) * self.kx * self.scale
        y = self.box[3] / 2 - (lat - self.cy) * self.scale
        return x, y

    def _land(self, spec):
        rings = load_rings(spec["geojson"])
        w, h = round(self.box[2]), round(self.box[3])
        sea, land = rgb(spec.get("sea", "marinho")), rgb(spec.get("land", "marinho_claro"))
        coast = rgb(spec.get("coast", "creme"))

        def paint(d, m):
            d.rectangle((0, 0, w * m, h * m), fill=sea + (255,))
            for ring in rings:
                pts = [tuple(v * m for v in self.project(lon, lat)) for lon, lat in ring]
                if len(pts) >= 3:
                    d.polygon(pts, fill=land + (255,), outline=coast + (255,))
            if spec.get("grid", True):
                grid = rgb(spec.get("grid_color", "noite")) + (60,)
                for lon in range(-180, 181, 10):
                    x = self.project(lon, 0)[0] * m
                    d.line((x, 0, x, h * m), fill=grid, width=m)
                for lat in range(-80, 81, 10):
                    y = self.project(0, lat)[1] * m
                    d.line((0, y, w * m, y), fill=grid, width=m)
        return supersampled((w, h), paint, 2).convert("RGB")

    def draw(self, frame, t, frame_index):
        st = self.state(t)
        if st is None:
            return
        s = self.ctx.s
        w, h = self.base.size
        layer = self.base.copy()
        m = 2
        over = Image.new("RGBA", (w * m, h * m), (0, 0, 0, 0))
        d = ImageDraw.Draw(over)
        for ring in self.rings:
            age = t - ring["t0"]
            if age < 0:
                continue
            cx, cy = self.project(*ring["at"])
            period, count = float(ring.get("period", 2.4)), int(ring.get("count", 3))
            for i in range(count):
                if age / period - i / count < 0:
                    continue
                phase = (age / period - i / count) % 1.0
                r = phase * float(ring.get("radius", 520)) * s
                alpha = int(255 * (1 - phase) ** 1.2)
                lw = max(2, round(8 * s)) * m
                d.ellipse(((cx - r) * m, (cy - r) * m, (cx + r) * m, (cy + r) * m),
                          outline=rgb(ring.get("color", "ouro")) + (alpha,), width=lw)
        for route in self.routes:
            if t < route["t0"]:
                continue
            p = ease((t - route["t0"]) / float(route.get("draw", 1.2)))
            ax, ay = self.project(*route["from"])
            bx, by = self.project(*route["to"])
            mx, my = (ax + bx) / 2, (ay + by) / 2
            bend = float(route.get("bend", 0.18))
            qx, qy = mx - (by - ay) * bend, my + (bx - ax) * bend
            n = 40
            pts = [(((1 - u) ** 2 * ax + 2 * (1 - u) * u * qx + u * u * bx) * m,
                    ((1 - u) ** 2 * ay + 2 * (1 - u) * u * qy + u * u * by) * m)
                   for u in (i / n for i in range(int(n * p) + 1))]
            color = rgb(route.get("color", "creme")) + (255,)
            if len(pts) > 1:
                d.line(pts, fill=color, width=max(2, round(6 * s)) * m, joint="curve")
            if p >= 1:
                r = 9 * s * m
                d.ellipse((bx * m - r, by * m - r, bx * m + r, by * m + r), fill=color)
        for pt in self.points:
            x, y = self.project(*pt["at"])
            pulse = 1 + 0.18 * math.sin(t * math.tau / 1.4)
            r = float(pt.get("radius", 14)) * s * pulse * m
            d.ellipse((x * m - r, y * m - r, x * m + r, y * m + r), fill=rgb(pt.get("color", "ouro")) + (255,),
                      outline=rgb("creme") + (255,), width=max(2, round(3 * s)) * m)
        over = over.resize((w, h), Image.LANCZOS)
        layer.paste(over, (0, 0), over)
        d2 = ImageDraw.Draw(layer)
        labelled = self.points + [r for r in self.routes if r.get("label") and t >= r["t0"] + float(r.get("draw", 1.2))]
        for item in labelled:
            if not item.get("label"):
                continue
            x, y = self.project(*(item.get("at") or item["to"]))
            dx, dy = item.get("label_offset", [22, -30])
            d2.text((x + dx * s, y + dy * s), item["label"], font=self.label_font, fill=rgb("creme"),
                    stroke_width=max(2, round(4 * s)), stroke_fill=rgb("noite"))
        if self.credit:
            cf = theme.font("credito", max(8, round(24 * s)))
            d2.text((w - 20 * s, h - 16 * s), self.credit, font=cf, fill=rgb("creme"), anchor="rd")
        dim = float(self.spec.get("dim", 0.0))
        if self.t_dim is not None:
            dim *= ease((t - self.t_dim) / 0.8)
        if dim > 0:
            layer = Image.blend(layer, Image.new("RGB", layer.size, rgb("noite")), dim)
        pos = (round(self.box[0]), round(self.box[1]))
        if st[0] < 0.999:
            region = frame.crop((pos[0], pos[1], pos[0] + w, pos[1] + h))
            layer = Image.blend(region, layer, st[0])
        frame.paste(layer, pos)

    def sources(self):
        path = ROOT / self.spec["geojson"]
        return [path, path.parent / "PROVENANCE.yaml"]
