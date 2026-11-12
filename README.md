# Caderno Curioso — vídeo

Produção audiovisual do **Caderno Curioso** (newsletter de divulgação científica) para o
YouTube, com custo adicional zero: Python + Pillow + NumPy + PyYAML + FFmpeg, episódios
declarados em YAML, narração sintética gratuita (Fase 2) e QA automático + revisão humana.

**Estado: Fase 1 (fundação).** Nada aqui é vídeo aprovado. Leia `AGENTS.md` antes de trabalhar.

## Formatos planejados
- **Em Profundidade** — um tema por episódio, 8–15 min.
- **Giro da Ciência** — notícias da edição em blocos, 6–10 min.

Ambos: português do Brasil, 1920×1080, 30 fps, H.264 + AAC, legendas SRT.

## Uso
```bash
pip install -r requirements-dev.txt          # FFmpeg precisa estar instalado no sistema
python -m pytest -q                          # testes (inclui um render real de 360p)
python scripts/make_smoke_audio.py           # áudio sintético do episódio de teste
python -m engine.render episodes/_smoke --profile preview    # 720p rápido
python -m engine.render episodes/_smoke --profile entrega    # 1080p
python -m qa.run episodes/_smoke --profile entrega           # QA + folha de contato
python -m engine.render episodes/_smoke --still 1.5          # um quadro PNG
python scripts/font_specimen.py                              # comparar fontes candidatas
```
Saídas em `renders/<slug>/` (fora do git): `<slug>_<altura>p.mp4`, `.srt`, `.render.json` e
`qa_<altura>p/` (`relatorio.md`, `validation.json`, `folha_de_contato.jpg`).

## Estrutura
```
engine/      motor: tema, linha do tempo, camadas, render segmentado com cache
  layers/    text, picture, highlight, map, logo, fill
qa/          QA automático (formato, imagem, áudio, sincronia, legibilidade, legendas, direitos, fontes)
subtitles/   geração e validação de SRT
align/       tempos por palavra (faster-whisper, opcional) + reconciliação com o roteiro
brand/       theme.yaml (cores da logo, fontes por papel) e fontes OFL
assets/      material externo, sempre com PROVENANCE.yaml
episodes/    um diretório por episódio: episode.yaml, scenes/, timing/, fontes.yaml, roteiro.md
scripts/     utilitários (áudio de teste, dados geográficos, especímen de fontes, estimativa)
docs/        auditoria, decisões, checklist humano e relatórios de QA
```

## Episódio em YAML (resumo)
```yaml
# episodes/<ep>/episode.yaml
title: "..."
slug: meu_episodio
fps: 30
timing: timing/words.json         # tempos por palavra da narração
audio: {loudnorm: -16, tracks: [{file: audio/narracao.wav, words: narracao, start: 0}]}
scenes:
  - {file: scenes/01_abertura.yaml, start: 0.0, end: 6.2}
  - {file: scenes/02_contexto.yaml, start: 6.2, end: 14.0, transition: {type: crossfade, duration: 0.5}}
```
```yaml
# episodes/<ep>/scenes/01_abertura.yaml
name: "01 — Abertura"
background: marinho                # nome de cor do tema ou #RRGGBB
layers:
  - {type: text, text: "Uma pergunta", font: titulo, size: 96, color: creme,
     pos: [960, 540], anchor: mm, in: "w:pergunta", slide: [0, 24]}
```
Tempos: `1.5`, `"start+0.5"`, `"end-1"`, `"abs:12.3"`, `"w:palavra"`, `"w:palavra#2.end+0.2"`.

## Custos — regras
- Nenhuma API paga ou serviço tarifado. Nenhuma publicação automática no YouTube.
- GitHub Actions: **só execução manual**, uma por vez, 20 min no máximo, artifacts por 2 dias,
  com conferência de cota obrigatória antes do render. Repositório privado consome minutos e
  armazenamento do plano: confira em Settings → Billing.
- O 1080p de episódios longos deve ser renderizado localmente quando não couber na cota.
- MP4s nunca vão para o git.

## Licença
Código: MIT (ver `LICENSE`). Conteúdo editorial, marca e vídeos: todos os direitos reservados.
Terceiros: `NOTICE.md`.
