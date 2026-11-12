"""Registro de fontes científicas (fontes.yaml) e marcadores [F:id] do roteiro.

Formato de episodes/<ep>/fontes.yaml:

  fontes:
    - id: bepica_site
      titulo: "Beyond EPICA — Oldest Ice"
      autor: "Consórcio Beyond EPICA (CNR-ISP, coord.)"   # autor ou instituição
      data: 2026-05-03            # data da publicação; "desconhecida" se não houver
      url: "https://www.beyondepica.eu/en/"
      tipo_evidencia: site_institucional
      status: preliminar          # preliminar | consolidado
      acesso: integral            # integral | parcial | resumo | nao_acessado
      afirmacoes: ["testemunho de 2,8 km", "gelo de pelo menos 1,2 milhão de anos"]
      limitacoes: "resultados apresentados em congresso, sem revisão por pares"
      verificado_em: 2026-11-12

Episódios sem conteúdo factual (ex.: testes técnicos) usam `nao_aplicavel: "<motivo>"`.
Nada aqui verifica se uma afirmação é verdadeira: isso é revisão humana.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

TIPOS = {"artigo_revisado", "preprint", "anuncio_congresso", "comunicado_imprensa", "reportagem",
         "dados_oficiais", "site_institucional", "livro"}
STATUS = {"preliminar", "consolidado"}
ACESSO = {"integral", "parcial", "resumo", "nao_acessado"}
CAMPOS = ("id", "titulo", "autor", "data", "url", "tipo_evidencia", "status", "afirmacoes", "limitacoes",
          "acesso", "verificado_em")
MARKER = re.compile(r"\[F:([\w\-, ]+)\]")


def load(episode_dir: Path) -> dict | None:
    path = Path(episode_dir) / "fontes.yaml"
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def check(episode_dir: Path) -> dict:
    """{'falhas': [...], 'avisos': [...], 'info': [...]}"""
    falhas, avisos, info = [], [], []
    data = load(episode_dir)
    if data is None:
        return {"falhas": ["fontes.yaml ausente"], "avisos": [], "info": []}
    if data.get("nao_aplicavel"):
        info.append(f"sem conteúdo factual: {data['nao_aplicavel']}")
        return {"falhas": [], "avisos": [], "info": info}
    fontes = data.get("fontes") or []
    if not fontes:
        falhas.append("fontes.yaml sem nenhuma fonte")
    ids = set()
    for i, f in enumerate(fontes, 1):
        label = f"fonte {f.get('id') or i}"
        for c in CAMPOS:
            if f.get(c) in (None, "", []):
                falhas.append(f"{label}: campo ausente '{c}'")
        if f.get("id") in ids:
            falhas.append(f"{label}: id repetido")
        ids.add(f.get("id"))
        if f.get("tipo_evidencia") and f["tipo_evidencia"] not in TIPOS:
            falhas.append(f"{label}: tipo_evidencia inválido {f['tipo_evidencia']!r}")
        if f.get("status") and f["status"] not in STATUS:
            falhas.append(f"{label}: status inválido {f['status']!r}")
        if f.get("acesso") and f["acesso"] not in ACESSO:
            falhas.append(f"{label}: acesso inválido {f['acesso']!r}")
        if f.get("tipo_evidencia") in ("preprint", "anuncio_congresso") and f.get("status") != "preliminar":
            falhas.append(f"{label}: {f['tipo_evidencia']} precisa de status 'preliminar'")
        if f.get("status") == "preliminar":
            avisos.append(f"{label}: preliminar — conferir selo/aviso na tela (revisão humana)")
        if f.get("acesso") in ("resumo", "nao_acessado"):
            avisos.append(f"{label}: texto integral não lido ({f['acesso']})")
        if f.get("url") and not str(f["url"]).startswith(("http://", "https://")):
            falhas.append(f"{label}: url inválida")
    roteiro = Path(episode_dir) / "roteiro.md"
    if roteiro.exists():
        text = roteiro.read_text(encoding="utf-8")
        used = {x.strip() for m in MARKER.findall(text) for x in m.split(",")}
        for ref in sorted(used - ids):
            falhas.append(f"roteiro cita [F:{ref}], que não está em fontes.yaml")
        for ref in sorted(ids - used):
            avisos.append(f"fonte {ref} não é citada no roteiro")
        paras = [p for p in re.split(r"\n\s*\n", text) if p.strip() and not p.lstrip().startswith("#")]
        bare = [p for p in paras if re.search(r"\d", MARKER.sub("", p)) and not MARKER.search(p)]
        if bare:
            avisos.append(f"{len(bare)} parágrafo(s) com números e sem marcador [F:id]")
        info.append(f"{len(used)} fonte(s) citadas no roteiro")
    else:
        info.append("sem roteiro.md: marcadores [F:id] não verificados")
    return {"falhas": falhas, "avisos": avisos, "info": info}
