# Avisos de origem e licenças de terceiros

## Código adaptado do projeto Reforma (mesmo autor)
Fonte: `GustavoHenriquePestana/reformaProtestante-`, branch `claude/cool-fermi-9erehz`,
commit `4b8f111fbe413b432427c9377f74679bba17bf44`. Reaproveitamento **autorizado por escrito
pelo autor em 12/11/2026**. O repositório original não foi alterado.

| Aqui | Adaptado de | O que mudou |
|---|---|---|
| `engine/timeline.py` | `pipeline/timeline.py` | quase igual; registra borda da âncora |
| `engine/layers/base.py`, `text.py`, `picture.py`, `highlight.py`, `map.py` | `pipeline/layers.py` | sem pixel art, sem pergaminho, tema por nomes; texto com tracking; imagem com proveniência, crédito e rótulo; mapa aceita GeoJSON |
| `engine/render.py` | `pipeline/render.py` | sem kit de áudio; render segmentado com cache; transições; perfis |
| `subtitles/srt.py` | `pipeline/subtitles.py` | 2×42 caracteres, CPS, validador |
| `align/transcribe.py` | `pipeline/transcribe.py` | modelo configurável; reconciliação com o roteiro |
| `qa/run.py`, `qa/media.py` | `pipeline/qa.py` | removidos testes de pixel art/kit; acrescentados loudness, clipping, silêncios, legendas, direitos e fontes |

**Não foi copiado nada além de código:** nenhuma arte, fonte, imagem histórica, mapa,
áudio, kit, storyboard ou documento da Reforma. `tests/test_repo_rules.py` confere isso
contra `tests/data/reforma_asset_hashes.txt` (só hashes SHA-256, sem conteúdo).

## Fontes tipográficas (SIL Open Font License 1.1) — `brand/fonts/`
Arquivos baixados de `github.com/google/fonts` (12/11/2026), sem modificação (só o nome do
arquivo foi simplificado). Licença completa ao lado de cada família.
- Libre Caslon Text — © 2018 The Libre Caslon Text Project Authors
- Source Serif 4 — © 2014 The Source Serif 4 Project Authors
- Crimson Pro — © 2018 The Crimson Pro Project Authors
- Source Sans 3 — © 2010-2020 Adobe, Reserved Font Name "Source"

## Dados
- `assets/geo/ne_110m_land.json` — Natural Earth (domínio público). Ver `assets/geo/PROVENANCE.yaml`.

## Ferramentas externas (não distribuídas aqui)
FFmpeg (LGPL/GPL, chamado como programa externo); Python; Pillow (MIT-CMU), NumPy (BSD-3),
PyYAML (MIT), pytest (MIT); opcional: faster-whisper (MIT) e modelos Whisper (MIT).
