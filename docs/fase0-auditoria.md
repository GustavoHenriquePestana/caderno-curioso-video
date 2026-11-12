# Fase 0 — Auditoria e plano (aprovado em 12/11/2026)

Legenda: **[F]** fato verificado · **[H]** hipótese a verificar · **[P]** decisão pendente.

## 1. Repositório de referência (somente leitura)
`GustavoHenriquePestana/reformaProtestante-`, branch `claude/cool-fermi-9erehz`, commit
`4b8f111f`. **[F]** Sem arquivo LICENSE (direitos do autor, que autorizou o reaproveitamento).
**[F]** Pipeline Python + Pillow + FFmpeg; render 1080p de 82,7 s levou 3 min 14 s no Actions
(≈ 2,35 s/s). **[F]** Acoplamentos removidos aqui: kit de áudio privado com SHA-256 fixo,
fontes e pergaminho do pack01, pixel art 640×360, paleta da Reforma, workflow com gatilho `push`.
**[F]** Não copiados: `SucoTeologico_CodexCloud_Kit.zip` (voz do autor, storyboard, prompts),
`assets/art/`, `art-library/`, imagens históricas, `europa_land.json`, EB Garamond, scripts do pack01.

## 2. Narração (Fase 2) — comparativo inicial
| Modelo | pt-BR masculino | Licença | Observação |
|---|---|---|---|
| Piper (OHF-Voice/piper1-gpl) | **[F]** `faber-medium` (dataset CC0 no model card), `edresson-low` (CC BY 4.0) | motor GPL-3.0; voz por voz | **[H]** leve e rápido em CPU |
| Kokoro-82M | **[F]** `pm_alex`, `pm_santa` | pesos Apache-2.0; G2P via espeak-ng (GPL) | **[F]** sem nota de qualidade pt-BR publicada |
| Chatterbox Multilingual | **[F]** português (fine-tune pt-BR anunciado) | **[F]** MIT; marca d'água PerTh | **[H]** pesado em CPU de 8 GB; clonagem só com voz autorizada |
| Excluídos | — | XTTS-v2 (CPML), F5-TTS (CC-BY-NC), MMS-TTS (CC-BY-NC), Fish Speech (CC-BY-NC-SA), edge-tts (serviço não oficial) | incompatíveis com monetização |

Três amostras com o mesmo texto (A: Piper faber; B: Kokoro pm_alex; C: Chatterbox com voz do
autor ou outra voz Piper). Normalização de números, unidades, siglas, dicionário de
pronúncia e pausas. **A aprovação auditiva é só humana.**

## 3. Piloto — gelo de 1,2 milhão de anos (edição #1)
Texto da edição lido pelo Google Docs. Conferido no site oficial do Beyond EPICA (12/11/2026):
- **[F]** testemunho de 2,8 km; gelo de pelo menos 1,2 milhão de anos; Little Dome C a 35 km de
  Concordia, 3.200 m de altitude; −35 °C médios na campanha de verão; 12 instituições de 10
  países; projeto 2019–2027; sessão de resultados na EGU (Viena, 3–8/05/2026); transição do
  Pleistoceno Médio entre 0,9 e 1,2 milhão de anos (ciclos de 40 mil → 100 mil anos).
- **Corrigir na newsletter/roteiro:** "a 12000 km do polo sul" (impossível; a fonte diz 35 km de
  Concordia); "mais de 100 cientistas" (não encontrado); "essa semana chegou ao objetivo"
  (o marco foi anunciado antes; em maio de 2026 vieram os primeiros resultados); "as bolhas
  guardam temperatura" (temperatura vem dos isótopos da água do gelo); grafia "Beyound".
- **[H]** "queda do CO₂ é o principal gatilho": só a Nature poderia sustentar; página exige
  login — tratar como "resultado preliminar sugere" até leitura da fonte.

## 4. Fases e pontos de aprovação
| Fase | Entregas | Aceite | Parada |
|---|---|---|---|
| 0 | este plano | aprovação do autor | ✅ aprovado |
| 1 Fundação | estrutura, código adaptado, tema, testes, workflows manuais, render de teste | testes verdes; render 720p/1080p + QA; sem assets da Reforma; sem gatilho `push` | ✋ validação |
| 2 TTS | normalizador + dicionário, 3 amostras, relatório de RAM/tempo/licença | amostras medidas; aprovação auditiva humana | ✋ escuta |
| 3 Piloto | fontes.yaml, roteiro 60–90 s, storyboard, YAML, 720p → 1080p, SRT, QA | afirmações com fonte, imagens com licença, QA verde; aprovação audiovisual humana | ✋ |
| 4 Templates | Em Profundidade e Giro; gráficos, diagramas, linhas do tempo, créditos | exemplo de cada formato dentro da cota | ✋ |
| 5 Produção | dois vídeos completos | revisão humana científica e audiovisual; nada publicado automaticamente | ✋ |

## 5. Custos
Tudo gratuito. Actions só manual, 1 por vez, 20 min, artifacts por 2 dias, conferência de cota
obrigatória. **[H]** Plano Free em repositório privado ≈ 2.000 min/mês e ≈ 500 MB de
armazenamento — conferir em Settings → Billing. 1080p de episódios longos: render local.
