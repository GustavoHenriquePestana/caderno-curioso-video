from subtitles import srt


def words(text, start=0.0, step=0.42):
    out = []
    for i, w in enumerate(text.split()):
        out.append({"w": w, "start": round(start + i * step, 3), "end": round(start + i * step + 0.3, 3)})
    return out


def test_generated_srt_is_valid(tmp_path):
    ws = words("Num ponto da Antártida Oriental, pesquisadores retiraram um cilindro de gelo muito "
               "comprido. As bolhas presas nele são amostras de atmosfera antiga.")
    path = srt.write_srt(ws, tmp_path / "x.srt")
    res = srt.validate(path.read_text(encoding="utf-8"), duration=30, words=ws)
    assert res["falhas"] == []
    for cue in srt.parse_srt(path.read_text(encoding="utf-8")):
        assert len(cue["lines"]) <= 2
        assert all(len(line) <= 42 for line in cue["lines"])


def test_validate_catches_problems():
    bad = ("1\n00:00:01,000 --> 00:00:03,000\nlinha que passa muito do limite de quarenta e dois\n\n"
           "3\n00:00:02,500 --> 00:00:02,600\nsobreposta\n")
    res = srt.validate(bad, duration=2.0)
    text = " ".join(res["falhas"])
    assert "numeração" in text and "sobrepõe" in text and "caracteres" in text and "depois do vídeo" in text


def test_split_lines_balanced():
    lines = srt.split_lines("as glaciações ficaram mais longas, mais severas e mais espaçadas")
    assert len(lines) == 2 and all(len(x) <= 42 for x in lines)
