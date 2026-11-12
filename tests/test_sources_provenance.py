import yaml

from engine import provenance
from engine.theme import ROOT
from qa import sources


def test_smoke_is_declared_not_applicable():
    res = sources.check(ROOT / "episodes" / "_smoke")
    assert res["falhas"] == [] and res["info"]


def test_sources_validation(tmp_path):
    (tmp_path / "fontes.yaml").write_text(yaml.safe_dump({"fontes": [
        {"id": "a", "titulo": "T", "autor": "X", "data": "2026-05-03", "url": "https://x.org",
         "tipo_evidencia": "anuncio_congresso", "status": "consolidado", "afirmacoes": ["algo"],
         "limitacoes": "sem revisão", "acesso": "integral", "verificado_em": "2026-11-12"},
        {"id": "b", "titulo": "T2"},
    ]}, allow_unicode=True), encoding="utf-8")
    (tmp_path / "roteiro.md").write_text("O gelo tem 1,2 milhão de anos [F:a]. Outro dado: 35 km [F:zzz].",
                                         encoding="utf-8")
    res = sources.check(tmp_path)
    text = " ".join(res["falhas"])
    assert "precisa de status 'preliminar'" in text
    assert "campo ausente 'url'" in text
    assert "[F:zzz]" in text


def test_missing_sources_file_fails(tmp_path):
    assert sources.check(tmp_path)["falhas"] == ["fontes.yaml ausente"]


def test_provenance_rules():
    assert provenance.problems(None) == ["sem registro em PROVENANCE.yaml"]
    rec = {"titulo": "t", "autor": "a", "origem_url": "u", "licenca": "CC-BY-NC-4.0", "credito": "c",
           "natureza": "documental", "verificado_em": "2026-11-12"}
    assert any("não aceita" in p for p in provenance.problems(rec))
    rec["licenca"] = "CC-BY-4.0"
    assert provenance.problems(rec) == [] and provenance.needs_credit(rec)
    rec["licenca"] = "dominio-publico"
    assert not provenance.needs_credit(rec)


def test_geodata_has_provenance():
    rec = provenance.record_for(ROOT / "assets" / "geo" / "ne_110m_land.json")
    assert provenance.problems(rec) == []
