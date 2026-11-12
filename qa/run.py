"""QA automático de um episódio renderizado.

    python -m qa.run episodes/<episódio> [--profile preview|entrega|teste] [--height N]

Mede o que é mensurável e gera folha de contato + relatório para a avaliação humana.
Passar aqui NÃO é aprovação: o status do vídeo continua "aguardando revisão humana".

Estrutura adaptada de reformaProtestante-/pipeline/qa.py (commit 4b8f111); verificações de
pixel art e do kit privado foram removidas; loudness, clipping, silêncios, legendas,
direitos e fontes científicas foram acrescentados.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from engine import provenance, theme
from engine.layers import Map, Picture, Text
from engine.render import PROFILES, Episode
from engine.theme import ROOT
from subtitles import srt as srtlib

from . import media, sources

DEFAULTS = {
    "loudness_lufs": -16.0, "loudness_tol": 1.0, "true_peak_max": -1.0,
    "max_static_s": 2.0, "max_silence_s": 2.5, "min_text_px": 40, "min_credit_px": 24,
    "min_contrast": 4.5, "safe_margin": 0.05,
}
OK, AVISO, FALHA, NA = "ok", "aviso", "falha", "n/a"


class Report:
    def __init__(self):
        self.checks = []

    def add(self, category, name, status, detail):
        if status is True:
            status = OK
        elif status is False:
            status = FALHA
        self.checks.append({"categoria": category, "verificacao": name, "status": status, "detalhe": detail})
        print(f"{status.upper():6} [{category}] {name} — {detail}")

    def from_lists(self, category, name, res, ok_detail):
        if res["falhas"]:
            self.add(category, name, FALHA, "; ".join(res["falhas"]))
        elif res["avisos"]:
            self.add(category, name, AVISO, "; ".join(res["avisos"]))
        else:
            self.add(category, name, OK, ok_detail)

    @property
    def failed(self):
        return any(c["status"] == FALHA for c in self.checks)


def run(episode_dir, profile="preview", height=None):
    height = height or PROFILES[profile]["height"]
    ep = Episode(episode_dir, height)
    cfg = dict(DEFAULTS, **(ep.spec.get("qa") or {}))
    video = ep.output()
    if not video.exists():
        raise SystemExit(f"vídeo não encontrado: {video} — renderize antes")
    qa_dir = ep.out_dir / f"qa_{height}p"
    (qa_dir / "quadros").mkdir(parents=True, exist_ok=True)
    rep = Report()
    s = ep.size

    # 1. Formato ---------------------------------------------------------------
    info = media.probe(video)
    vs = [x for x in info["streams"] if x["codec_type"] == "video"]
    au = [x for x in info["streams"] if x["codec_type"] == "audio"]
    v = vs[0]
    rep.add("formato", "dimensões", (v["width"], v["height"]) == s, f"{v['width']}x{v['height']} (esperado {s[0]}x{s[1]})")
    rep.add("formato", f"{ep.fps} fps constantes", v["r_frame_rate"] == f"{ep.fps}/1", v["r_frame_rate"])
    rep.add("formato", "codec H.264 yuv420p", v["codec_name"] == "h264" and v.get("pix_fmt") == "yuv420p",
            f"{v['codec_name']} {v.get('profile', '')} {v.get('pix_fmt')}")
    nb = int(v.get("nb_frames", 0))
    rep.add("formato", "número de quadros", nb == ep.frames, f"{nb} (esperado {ep.frames})")
    dur = float(info["format"]["duration"])
    rep.add("formato", "duração", abs(dur - ep.frames / ep.fps) <= 1.5 / ep.fps + 0.03,
            f"{dur:.3f}s (esperado {ep.frames / ep.fps:.3f}s)")
    rep.add("formato", "faststart (moov antes de mdat)", media.faststart(video), "pronto para streaming")
    rep.add("audio", "faixa de áudio presente", len(au) == 1,
            f"{au[0]['codec_name']} {au[0]['sample_rate']} Hz {au[0].get('channels')} canais" if au else "ausente")
    if au:
        a = au[0]
        rep.add("audio", "AAC 48 kHz", a["codec_name"] == "aac" and a["sample_rate"] == "48000",
                f"{a['codec_name']} {a['sample_rate']} Hz")
        adur = float(a.get("duration", dur))
        rep.add("audio", "áudio cobre o vídeo", abs(adur - dur) <= 0.1, f"áudio {adur:.3f}s, vídeo {dur:.3f}s")

    # 2. Imagem em movimento -----------------------------------------------------
    frames = ep_frames = media.gray_frames(video)
    distinct = len({hashlib.md5(f.tobytes()).hexdigest() for f in frames})
    diffs = np.abs(frames[1:].astype(np.int16) - frames[:-1].astype(np.int16)).mean(axis=1)
    runs, cur, start = [], 0, 0
    for i, d in enumerate(diffs, 1):
        if d < 0.05:  # praticamente idênticos (ruído de compressão fica abaixo disso)
            if cur == 0:
                start = i - 1
            cur += 1
        else:
            if cur:
                runs.append((start, cur + 1))
            cur = 0
    if cur:
        runs.append((start, cur + 1))
    bad = []
    for f0, n in runs:
        scene = ep.scene_at(f0 / ep.fps)
        if n / ep.fps > cfg["max_static_s"] and not scene.static_ok:
            bad.append(f"{f0 / ep.fps:.2f}s–{(f0 + n) / ep.fps:.2f}s ({scene.name})")
    longest = max((n for _, n in runs), default=1)
    rep.add("imagem", f"sem trecho congelado > {cfg['max_static_s']}s", not bad,
            "; ".join(bad) or f"maior trecho parado: {longest / ep.fps:.2f}s; {distinct} de {len(ep_frames)} quadros únicos")
    means = frames.mean(axis=1)
    blank = int(((means < 2) | (means > 253)).sum())
    rep.add("imagem", "quadros vazios (preto/branco total)", AVISO if blank > ep.fps else OK,
            f"{blank} quadro(s)")

    # 3. Áudio -------------------------------------------------------------------
    if au:
        loud = media.ebur128(video)
        target, tol = cfg["loudness_lufs"], cfg["loudness_tol"]
        rep.add("audio", f"loudness {target:+.0f} ± {tol:.0f} LUFS", abs(loud["I"] - target) <= tol,
                f"integrada {loud['I']:.1f} LUFS, faixa {loud['LRA']:.1f} LU")
        rep.add("audio", f"pico real ≤ {cfg['true_peak_max']} dBTP", loud["TP"] <= cfg["true_peak_max"],
                f"{loud['TP']:.1f} dBTP")
        samples = media.pcm(video, rate=48000, channels=2)
        clipped = int((np.abs(samples) >= 0.999).sum())
        rep.add("audio", "sem clipping digital", clipped == 0, f"{clipped} amostra(s) em ±0 dBFS")
        words = ep.timeline.words
        sil = media.silences(video)
        inside, long_sil = [], []
        for a0, a1 in sil:
            hit = [w for w in words if min(a1, w["end"]) - max(a0, w["start"]) > 0.15]
            if hit:
                inside.append(f"{a0:.2f}–{a1:.2f}s sobre “{hit[0]['w']}”")
            scene = ep.scene_at(a0)
            if a1 - a0 > cfg["max_silence_s"] and not scene.spec.get("silence_ok"):
                long_sil.append(f"{a0:.2f}–{min(a1, dur):.2f}s")
        rep.add("audio", "nenhum silêncio onde há fala prevista", not inside,
                "; ".join(inside) or f"{len(sil)} pausa(s) detectada(s), todas fora das palavras")
        rep.add("audio", f"sem silêncio inesperado > {cfg['max_silence_s']}s", AVISO if long_sil else OK,
                "; ".join(long_sil) or "nenhum")
        if words:
            mono = media.pcm(video, rate=16000)
            mute = []
            for w in words:
                seg = mono[int(w["start"] * 16000):int(w["end"] * 16000)]
                rms = float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0
                if rms < 10 ** (-45 / 20):
                    mute.append(w["w"])
            rep.add("sincronia", "há som em cada palavra marcada", not mute,
                    f"{len(mute)} palavra(s) mudas: {' '.join(mute[:8])}" if mute else f"{len(words)} palavras com sinal")

    # 4. Sincronia ---------------------------------------------------------------
    anchors = ep.timeline.anchors
    worst = 0.0
    for a in anchors:
        target_t = (a["word_end"] if a["edge"] == "end" else a["word_start"]) + a["offset"]
        a["frame_time"] = round(a["time"] * ep.fps) / ep.fps
        a["error_ms"] = round((a["frame_time"] - target_t) * 1000, 1)
        worst = max(worst, abs(a["error_ms"]))
    limit = 1000 / ep.fps / 2 + 1
    rep.add("sincronia", f"âncoras a ≤ {limit:.0f} ms da palavra", worst <= limit,
            f"{len(anchors)} âncora(s); maior desvio {worst:.0f} ms" if anchors else "nenhuma âncora em palavras")
    cuts = [(sc.name, sc.end, ep.timeline.cut_inside_word(sc.end)) for sc in ep.scenes[:-1]]
    badcuts = [f"{n} em {t:.2f}s corta “{w['w']}”" for n, t, w in cuts if w]
    rep.add("sincronia", "nenhum corte de cena dentro de palavra", not badcuts,
            "; ".join(badcuts) or f"{len(cuts)} corte(s), todos em pausas")

    # 5. Legibilidade ------------------------------------------------------------
    texts, problems = [], []
    m = cfg["safe_margin"]
    for scene in ep.scenes:
        for layer in scene.layers:
            if not isinstance(layer, Text):
                continue
            credit = layer.spec.get("role") == "credit"
            size_1080 = layer.font_px / ep.height * 1080
            dur_t = layer.t_out - layer.t_in
            chars = len("".join(layer.lines))
            t_mid = min(layer.t_in + max(layer.fade, 0.0) + 0.6, layer.t_out - 0.05)
            if layer.backed:
                img = np.asarray(layer.sprite.convert("RGB"))
                x0, y0 = round(layer.text_box[0] - layer.origin[0]), round(layer.text_box[1] - layer.origin[1])
                x1, y1 = round(layer.text_box[2] - layer.origin[0]), round(layer.text_box[3] - layer.origin[1])
            else:
                layer.enabled = False
                img = np.asarray(scene.render(t_mid, s))
                layer.enabled = True
                x0, y0, x1, y1 = (round(c) for c in layer.text_box)
            region = img[max(0, y0):max(1, y1), max(0, x0):max(1, x1)].reshape(-1, 3)
            if layer.backed:
                dist = np.abs(region.astype(np.int16) - np.array(layer.color)).sum(axis=1)
                region = region[dist > 120]
            sample = region[::max(1, len(region) // 4000)]
            ratios = sorted(media.contrast(layer.color, tuple(px)) for px in sample)
            ratio = ratios[len(ratios) // 10] if ratios else 0.0
            bx0, by0, bx1, by1 = layer.text_box
            safe = bx0 >= m * s[0] and by0 >= m * s[1] and bx1 <= (1 - m) * s[0] and by1 <= (1 - m) * s[1]
            item = {"cena": scene.name, "texto": " / ".join(layer.lines), "px_1080": round(size_1080),
                    "segundos": round(dur_t, 2), "caracteres": chars, "contraste_p10": round(ratio, 2),
                    "margem_segura": safe, "credito": credit}
            texts.append(item)
            min_px = cfg["min_credit_px"] if credit else cfg["min_text_px"]
            if size_1080 < min_px - 0.5:
                problems.append(f"“{item['texto']}” {round(size_1080)} px (< {min_px})")
            if dur_t < max(1.2, 0.06 * chars):
                problems.append(f"“{item['texto']}” {dur_t:.2f}s na tela (< {max(1.2, 0.06 * chars):.2f}s)")
            if ratio < cfg["min_contrast"]:
                problems.append(f"“{item['texto']}” contraste {ratio:.1f}:1")
            if not safe:
                problems.append(f"“{item['texto']}” fora da margem segura de {m:.0%}")
    rep.add("legibilidade", "tamanho, tempo, contraste e margem dos textos", not problems,
            "; ".join(problems) or f"{len(texts)} texto(s) dentro dos limites")

    # 6. Legendas ----------------------------------------------------------------
    srt_path = ep.output("srt")
    if ep.timeline.words:
        if srt_path.exists():
            res = srtlib.validate(srt_path.read_text(encoding="utf-8"), dur, ep.timeline.words)
            rep.from_lists("legendas", "SRT válido (ordem, sobreposição, 2×42, CPS, cobertura)", res,
                           f"{res['cues']} legenda(s)")
        else:
            rep.add("legendas", "SRT presente", FALHA, f"{srt_path.name} ausente")
    else:
        rep.add("legendas", "SRT", NA, "episódio sem tempos de palavra")

    # 7. Direitos e integridade de imagens --------------------------------------
    rights, integrity = [], []
    used = 0
    for scene in ep.scenes:
        for layer in scene.layers:
            if isinstance(layer, Picture):
                used += 1
                rec = layer.record
                rights += [f"{layer.spec['file']}: {p}" for p in provenance.problems(rec)]
                if provenance.needs_credit(rec) and not layer.credit_shown:
                    rights.append(f"{layer.spec['file']}: licença {rec['licenca']} exige crédito na tela (credit: true)")
                if (rec or {}).get("natureza") == "ilustrativa" and not layer.label:
                    rights.append(f"{layer.spec['file']}: ilustração sem rótulo na tela")
                try:
                    with Image.open(layer.path) as im:
                        im.verify()
                except Exception as exc:  # noqa: BLE001
                    integrity.append(f"{layer.spec['file']}: {exc}")
                if layer.upscale > 1.3:
                    integrity.append(f"{layer.spec['file']}: ampliada {layer.upscale:.2f}× (perde nitidez)")
            elif isinstance(layer, Map):
                used += 1
                rights += [f"{layer.spec['geojson']}: {p}" for p in
                           provenance.problems(provenance.record_for(ROOT / layer.spec["geojson"]))]
    for font, lic in theme.font_files():
        if not font.exists():
            rights.append(f"fonte ausente: {font.relative_to(ROOT)}")
        elif not lic.exists() or "Open Font License" not in lic.read_text(encoding="utf-8", errors="ignore"):
            rights.append(f"{font.name}: licença OFL ausente")
    rep.add("direitos", "proveniência, licença, crédito e rótulos", not rights,
            "; ".join(rights) or f"{used} material(is) externo(s) e {len(theme.font_files())} arquivos de fonte com licença")
    rep.add("imagem", "integridade e resolução das imagens", AVISO if integrity else OK,
            "; ".join(integrity) or f"{sum(isinstance(la, Picture) for sc in ep.scenes for la in sc.layers)} imagem(ns)")
    blocked = reforma_hashes()
    if blocked:
        hits = []
        for scene in ep.scenes:
            for path in scene.sources():
                if path.exists() and path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() in blocked:
                    hits.append(str(path.relative_to(ROOT)))
        rep.add("direitos", "nenhum asset do projeto Reforma", not hits, "; ".join(hits) or f"{len(blocked)} hashes conferidos")

    # 8. Fontes científicas ------------------------------------------------------
    res = sources.check(ep.dir)
    rep.from_lists("ciencia", "registro de fontes (fontes.yaml) e marcadores do roteiro", res,
                   "; ".join(res["info"]) or "ok")

    # 9. Folha de contato --------------------------------------------------------
    times = sorted({round((sc.start + sc.end) / 2, 2) for sc in ep.scenes}
                   | {round(max(sc.start, sc.end - 0.3), 2) for sc in ep.scenes}
                   | {round(t, 2) for t in np.arange(0.5, dur, max(1.0, dur / 16))})
    times = [t for t in times if t < dur - 0.02]
    thumbs = []
    for t in times:
        out = qa_dir / "quadros" / f"t_{t:07.2f}s.jpg"
        media.extract_frame(video, t, out)
        thumbs.append((t, Image.open(out).convert("RGB")))
    cols, tw, th, pad = 4, 480, 270, 30
    rows = -(-len(thumbs) // cols)
    sheet = Image.new("RGB", (cols * tw, rows * (th + pad)), theme.rgb("noite"))
    d = ImageDraw.Draw(sheet)
    lf = theme.font("sans", 20)
    for i, (t, im) in enumerate(thumbs):
        x, y = (i % cols) * tw, (i // cols) * (th + pad)
        sheet.paste(im.resize((tw - 4, th - 4), Image.LANCZOS), (x + 2, y + pad))
        d.text((x + 6, y + 4), f"{t:.2f}s · {ep.scene_at(t).name}"[:48], font=lf, fill=theme.rgb("creme"))
    sheet.save(qa_dir / "folha_de_contato.jpg", quality=88)

    # 10. Relatório --------------------------------------------------------------
    counts = {k: sum(c["status"] == k for c in rep.checks) for k in (OK, AVISO, FALHA, NA)}
    render_info = ep.output("render.json")
    report = {
        "episodio": ep.spec.get("title"), "slug": ep.slug, "altura": height, "perfil": profile,
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "render": json.loads(render_info.read_text(encoding="utf-8")) if render_info.exists() else None,
        "resumo": counts, "automatico_passou": not rep.failed,
        "status_do_video": "AGUARDANDO REVISÃO HUMANA",
        "cenas": [{"nome": sc.name, "inicio": sc.start, "fim": sc.end, "status": sc.status} for sc in ep.scenes],
        "verificacoes": rep.checks, "textos": texts, "ancoras": anchors,
    }
    (qa_dir / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    write_markdown(qa_dir / "relatorio.md", report)
    print(f"\nAUTOMÁTICO: {counts[OK]} ok, {counts[AVISO]} aviso(s), {counts[FALHA]} falha(s)."
          "\nSTATUS DO VÍDEO: aguardando revisão humana (o QA automático nunca aprova).")
    return 1 if rep.failed else 0


def reforma_hashes() -> set[str]:
    path = ROOT / "tests" / "data" / "reforma_asset_hashes.txt"
    if not path.exists():
        return set()
    return {ln.split()[0] for ln in path.read_text(encoding="utf-8").splitlines() if ln and not ln.startswith("#")}


def write_markdown(dest: Path, r: dict):
    icon = {OK: "✅", AVISO: "⚠️", FALHA: "❌", NA: "—"}
    lines = [f"# QA — {r['episodio']} ({r['altura']}p, perfil {r['perfil']})", "",
             f"Gerado em {r['gerado_em']}.", "",
             "> **Status do vídeo: AGUARDANDO REVISÃO HUMANA.** O QA automático mede o que é mensurável;",
             "> ele não aprova vídeo, voz, ritmo, estética nem exatidão científica.", "",
             f"**Automático:** {r['resumo'][OK]} ok · {r['resumo'][AVISO]} aviso(s) · {r['resumo'][FALHA]} falha(s) · "
             f"{r['resumo'][NA]} não aplicável.", ""]
    if r.get("render"):
        ri = r["render"]
        cached = sum(1 for sgm in ri["segments"] if sgm["cached"])
        lines += [f"**Render:** {ri['frames']} quadros, {ri['duration']:.3f}s, {ri['seconds']}s de processamento, "
                  f"{ri['jobs']} processo(s), {cached}/{len(ri['segments'])} cena(s) do cache, commit `{ri['commit']}`.", ""]
    lines += ["## Verificações automáticas", "", "| | Categoria | Verificação | Detalhe |", "|---|---|---|---|"]
    for c in r["verificacoes"]:
        detail = c["detalhe"].replace("|", "\\|")
        lines.append(f"| {icon[c['status']]} | {c['categoria']} | {c['verificacao']} | {detail} |")
    lines += ["", "## Avaliação humana (pendente — preencher)", ""]
    checklist = ROOT / "docs" / "qa" / "CHECKLIST_HUMANO.md"
    if checklist.exists():
        lines += [ln for ln in checklist.read_text(encoding="utf-8").splitlines() if ln.startswith("- [ ]")]
    lines += ["", "Folha de contato: `folha_de_contato.jpg`. Quadros individuais em `quadros/`.", ""]
    dest.write_text("\n".join(lines), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description="QA automático de um episódio renderizado")
    ap.add_argument("episode")
    ap.add_argument("--profile", default="preview", choices=list(PROFILES))
    ap.add_argument("--height", type=int)
    args = ap.parse_args(argv)
    return run(args.episode, args.profile, args.height)


if __name__ == "__main__":
    sys.exit(main())
