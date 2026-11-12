from align.reconcile import reconcile, script_words


def test_script_words_strip_markup():
    text = "# Título\n\nO gelo tem 1,2 milhão de anos [F:bepica]. [pausa 0.4] Fim."
    assert script_words(text) == ["O", "gelo", "tem", "1,2", "milhão", "de", "anos", "Fim."]


def test_reconcile_keeps_script_spelling_and_times():
    script = ["O", "Beyond", "EPICA", "perfurou", "o", "gelo."]
    asr = [{"w": "O", "start": 0.0, "end": 0.1}, {"w": "biondi", "start": 0.15, "end": 0.5},
           {"w": "épica", "start": 0.55, "end": 0.9}, {"w": "perfurou", "start": 1.0, "end": 1.4},
           {"w": "o", "start": 1.45, "end": 1.5}, {"w": "gelo", "start": 1.55, "end": 1.9}]
    out, stats = reconcile(script, asr)
    assert [w["w"] for w in out] == script
    assert out[3]["start"] == 1.0 and out[-1]["end"] == 1.9
    assert (out[1]["start"], out[1]["end"]) == (0.15, 0.5)   # "biondi" → "Beyond": tempos herdados
    assert out[2]["start"] == 0.55                               # "épica" == "EPICA" após normalizar
    assert stats == {"iguais": 5, "redistribuidas": 1, "sem_tempo": 0}
