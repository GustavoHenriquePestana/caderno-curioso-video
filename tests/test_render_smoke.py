"""Render real (360p) do episódio de teste + QA automático. Requer FFmpeg."""
import json
import shutil
import subprocess
import sys

import pytest

from engine.render import Episode
from engine.theme import ROOT

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg ausente")
SMOKE = ROOT / "episodes" / "_smoke"


@pytest.fixture(scope="module")
def rendered():
    subprocess.run([sys.executable, str(ROOT / "scripts" / "make_smoke_audio.py"), str(SMOKE)], check=True)
    ep = Episode(SMOKE, 360)
    shutil.rmtree(ep.out_dir / "segmentos" / "360p", ignore_errors=True)
    final = ep.render("teste", jobs=1, log=lambda *a: None)
    return ep, final


def test_render_outputs(rendered):
    ep, final = rendered
    assert final.exists() and ep.output("srt").exists()
    info = json.loads(ep.output("render.json").read_text(encoding="utf-8"))
    assert info["frames"] == 135 and not any(s["cached"] for s in info["segments"])


def test_cache_reuses_segments(rendered):
    ep, _ = rendered
    ep.render("teste", jobs=1, log=lambda *a: None)
    info = json.loads(ep.output("render.json").read_text(encoding="utf-8"))
    assert all(s["cached"] for s in info["segments"])


def test_qa_passes_and_never_approves(rendered):
    from qa.run import run
    assert run(SMOKE, "teste", 360) == 0
    report = json.loads((rendered[0].out_dir / "qa_360p" / "validation.json").read_text(encoding="utf-8"))
    assert report["status_do_video"] == "AGUARDANDO REVISÃO HUMANA"
    assert (rendered[0].out_dir / "qa_360p" / "folha_de_contato.jpg").exists()


def test_transition_frames_blend(rendered):
    ep, _ = rendered
    mid = ep.frame(60)      # 2,0 s: meio do crossfade
    a = ep.scenes[0].render(1.99, ep.size)
    b = ep.scenes[1].render(2.0, ep.size)
    px = mid.getpixel((10, 10))
    assert px != a.getpixel((10, 10)) and px != b.getpixel((10, 10))
