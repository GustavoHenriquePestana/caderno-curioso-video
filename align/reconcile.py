"""Reconcilia o texto do roteiro com as palavras reconhecidas (só stdlib: difflib).

O reconhecimento de fala erra nomes, números e termos técnicos; o roteiro é a referência
do texto. Palavras iguais herdam os tempos; trechos divergentes têm os tempos do trecho
reconhecido redistribuídos pelo comprimento das palavras do roteiro.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from engine.timeline import norm

MARKUP = re.compile(r"\[(?:F|pausa|enfase|ênfase)[^\]]*\]|<!--.*?-->", re.S)


def script_words(text: str) -> list[str]:
    """Palavras faladas do roteiro (sem títulos markdown, marcadores [F:id], [pausa])."""
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    body = MARKUP.sub(" ", "\n".join(lines))
    return [w for w in body.split() if norm(w)]


def reconcile(script: list[str], asr: list[dict]) -> tuple[list[dict], dict]:
    a = [norm(w) for w in script]
    b = [w["key"] if "key" in w else norm(w["w"]) for w in asr]
    out: list[dict] = []
    stats = {"iguais": 0, "redistribuidas": 0, "sem_tempo": 0}
    for op, i0, i1, j0, j1 in SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op == "equal":
            for i, j in zip(range(i0, i1), range(j0, j1)):
                out.append({"w": script[i], "start": asr[j]["start"], "end": asr[j]["end"]})
            stats["iguais"] += i1 - i0
        elif op in ("replace", "insert") and i1 > i0:
            if j1 > j0:
                start, end = asr[j0]["start"], asr[j1 - 1]["end"]
            else:  # palavra do roteiro sem correspondente: encaixa no intervalo vizinho
                start = out[-1]["end"] if out else (asr[0]["start"] if asr else 0.0)
                end = asr[j0]["start"] if j0 < len(asr) else start + 0.3
                stats["sem_tempo"] += i1 - i0
            weights = [max(1, len(norm(w))) for w in script[i0:i1]]
            total, acc = sum(weights), 0
            for w, k in zip(script[i0:i1], weights):
                ws = start + (end - start) * acc / total
                acc += k
                out.append({"w": w, "start": round(ws, 3), "end": round(start + (end - start) * acc / total, 3)})
            stats["redistribuidas"] += i1 - i0
        # "delete": palavra reconhecida que não está no roteiro — descartada
    return out, stats
