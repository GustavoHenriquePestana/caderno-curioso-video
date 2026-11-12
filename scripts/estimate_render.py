"""Estima o tempo de render no GitHub Actions antes de gastar minutos.

    python scripts/estimate_render.py episodes/<ep> --perfil preview --limite 18

Fatores = segundos de processamento por segundo de vídeo, conservadores. Origem:
  * 1080p: 2,35 s/s medidos no projeto Reforma (Actions, 1 processo, 10/11/2026);
  * valores locais deste projeto ficam em renders/<slug>/render_*.json.
Atualize SEGUNDOS_POR_SEGUNDO quando houver medições reais neste repositório.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SEGUNDOS_POR_SEGUNDO = {"teste": 0.4, "preview": 1.3, "entrega": 3.0}
PREPARO_MIN = 2.5  # checkout, apt, pip, QA


def main(argv=None):
    from engine.render import PROFILES, Episode
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--perfil", default="preview", choices=list(PROFILES))
    ap.add_argument("--limite", type=float, default=18.0, help="minutos")
    args = ap.parse_args(argv)
    ep = Episode(args.episode, PROFILES[args.perfil]["height"])
    minutos = PREPARO_MIN + ep.duration * SEGUNDOS_POR_SEGUNDO[args.perfil] / 60
    print(f"{ep.slug}: {ep.duration:.1f}s de vídeo, {len(ep.scenes)} cenas, perfil {args.perfil} "
          f"→ estimativa {minutos:.1f} min de runner (limite {args.limite:.0f} min)")
    if minutos > args.limite:
        print("::error::Estimativa acima do limite. Renderize localmente ou divida o episódio.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
