import yaml
from PIL import Image

from engine.render import Episode
from engine.theme import ROOT


def make_episode(tmp_path, layers, background="marinho"):
    (tmp_path / "scenes").mkdir()
    (tmp_path / "scenes" / "a.yaml").write_text(yaml.safe_dump({"name": "a", "background": background,
                                                                 "layers": layers}, allow_unicode=True))
    (tmp_path / "episode.yaml").write_text(yaml.safe_dump({"title": "t", "slug": "teste_camadas", "fps": 30,
                                                           "scenes": [{"file": "scenes/a.yaml", "start": 0, "end": 2}]}))
    return Episode(tmp_path, 360)


def test_text_tracking_widens(tmp_path):
    ep = make_episode(tmp_path, [
        {"type": "text", "id": "a", "text": "CADERNO", "pos": [100, 100]},
        {"type": "text", "id": "b", "text": "CADERNO", "pos": [100, 300], "tracking": 0.2}])
    a, b = ep.scenes[0].ctx.layers["a"], ep.scenes[0].ctx.layers["b"]
    assert b.text_box[2] - b.text_box[0] > a.text_box[2] - a.text_box[0]


def test_picture_label_and_credit(tmp_path):
    asset = tmp_path / "img"
    asset.mkdir()
    Image.new("RGB", (400, 300), (200, 100, 50)).save(asset / "x.png")
    (asset / "PROVENANCE.yaml").write_text(yaml.safe_dump({"x.png": {
        "titulo": "t", "autor": "a", "origem_url": "https://x", "licenca": "CC-BY-4.0", "credito": "Foto: A (CC BY 4.0)",
        "natureza": "ilustrativa", "verificado_em": "2026-11-12"}}, allow_unicode=True))
    ep = make_episode(tmp_path, [{"type": "picture", "id": "p", "file": str(asset / "x.png"),
                                  "box": [200, 200, 800, 600], "credit": True}])
    p = ep.scenes[0].ctx.layers["p"]
    assert p.label == "Ilustração" and p.credit_shown


def test_map_and_logo_render(tmp_path):
    ep = make_episode(tmp_path, [
        {"type": "map", "geojson": "assets/geo/ne_110m_land.json", "box": [0, 0, 1920, 1080],
         "bbox": [-80, -40, -30, 10], "points": [{"at": [-46.6, -23.5], "label": "São Paulo"}], "credit": True},
        {"type": "logo", "pos": [1700, 200], "radius": 120, "draw": 0}])
    frame = ep.frame(30)
    assert frame.size == (640, 360)
    small = frame.resize((64, 36)).tobytes()
    assert len({small[i:i + 3] for i in range(0, len(small), 3)}) > 20
