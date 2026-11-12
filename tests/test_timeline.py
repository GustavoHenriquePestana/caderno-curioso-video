import pytest

from engine.timeline import Timeline, norm

EP = {"fps": 30, "audio": {"tracks": [{"words": "n", "start": 1.0, "trim_end": 5.0}]}}


@pytest.fixture
def tl(tmp_path):
    (tmp_path / "w.json").write_text(
        '{"n": [{"w": "Gelo", "start": 0.5, "end": 0.9}, {"w": "antigo,", "start": 1.0, "end": 1.4},'
        ' {"w": "gelo", "start": 2.0, "end": 2.3}, {"w": "corte", "start": 6.0, "end": 6.5}]}', encoding="utf-8")
    return Timeline(dict(EP, timing="w.json"), tmp_path)


def test_norm():
    assert norm("Milhão,") == "milhao"
    assert norm("CO₂") == "co2"  # NFKD converte o subscrito


def test_offsets_and_trim(tl):
    assert [w["start"] for w in tl.words] == [1.5, 2.0, 3.0]  # deslocado 1 s; "corte" após trim_end


def test_resolve_forms(tl):
    assert tl.resolve(0.5, 1.0, 4.0) == 1.5
    assert tl.resolve("start+0.25", 1.0, 4.0) == 1.25
    assert tl.resolve("end-1", 1.0, 4.0) == 3.0
    assert tl.resolve("abs:2.5", 1.0, 4.0) == 2.5
    assert tl.resolve("w:gelo", 1.0, 4.0) == 1.5
    assert tl.resolve("w:gelo#2", 1.0, 4.0) == 3.0
    assert tl.resolve("w:antigo.end+0.1", 1.0, 4.0) == pytest.approx(2.5)
    assert len(tl.anchors) == 3


def test_resolve_errors(tl):
    with pytest.raises(ValueError):
        tl.resolve("w:inexistente", 1.0, 4.0)
    with pytest.raises(ValueError):
        tl.resolve("depois", 1.0, 4.0)


def test_cut_inside_word(tl):
    assert tl.cut_inside_word(1.7)["w"] == "Gelo"
    assert tl.cut_inside_word(1.95) is None
