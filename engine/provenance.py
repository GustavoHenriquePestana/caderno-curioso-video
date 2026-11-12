"""Proveniência e licença de material externo (imagens, dados geográficos).

Cada pasta de assets tem um PROVENANCE.yaml que mapeia nome de arquivo → registro:

  gelo.jpg:
    titulo: "..."
    autor: "..."                 # pessoa ou instituição
    origem_url: "https://..."
    licenca: CC-BY-4.0           # ver LICENCAS abaixo
    licenca_url: "https://..."
    credito: "Foto: Fulano / Instituição (CC BY 4.0)"   # texto exibido na tela
    natureza: documental         # documental | ilustrativa | dados | propria
    alteracoes: "recorte, redimensionamento"
    verificado_em: 2026-11-12
    verificado_por: "nome"

Nunca considere uma imagem liberada só porque está na internet.
"""
from __future__ import annotations

from pathlib import Path

import yaml

# licença → exige crédito na tela?
LICENCAS = {
    "dominio-publico": False,
    "CC0-1.0": False,
    "CC-BY-4.0": True,
    "CC-BY-SA-4.0": True,
    "propria": False,            # material criado pelo próprio projeto
    "permissao-escrita": True,   # exige o documento de permissão em `permissao`
}
NATUREZAS = {"documental", "ilustrativa", "dados", "propria"}
CAMPOS = ("titulo", "autor", "origem_url", "licenca", "credito", "natureza", "verificado_em")


def record_for(path: Path) -> dict | None:
    prov = path.parent / "PROVENANCE.yaml"
    if not prov.exists():
        return None
    data = yaml.safe_load(prov.read_text(encoding="utf-8")) or {}
    rec = data.get(path.name)
    return dict(rec) if isinstance(rec, dict) else None


def problems(rec: dict | None) -> list[str]:
    if rec is None:
        return ["sem registro em PROVENANCE.yaml"]
    out = [f"campo ausente: {c}" for c in CAMPOS if not rec.get(c)]
    lic = rec.get("licenca")
    if lic and lic not in LICENCAS:
        out.append(f"licença não aceita: {lic!r} (aceitas: {', '.join(LICENCAS)})")
    if lic == "permissao-escrita" and not rec.get("permissao"):
        out.append("licença 'permissao-escrita' sem o documento em `permissao`")
    if rec.get("natureza") and rec["natureza"] not in NATUREZAS:
        out.append(f"natureza inválida: {rec['natureza']!r}")
    return out


def needs_credit(rec: dict | None) -> bool:
    return bool(rec) and LICENCAS.get(rec.get("licenca"), True)
