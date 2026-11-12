# Instruções para agentes — Caderno Curioso Video

## Missão
Transformar edições da newsletter Caderno Curioso em vídeos do YouTube (formatos
**Em Profundidade** e **Giro da Ciência**), com custo adicional zero, qualidade científica
verificável e aprovação humana em cada fase.

## Regras inegociáveis
1. **Custo zero.** Proibido usar APIs pagas, serviços tarifados ou criar infraestrutura com
   cobrança automática sem autorização explícita do autor. Nada de Remotion, Runway etc.
2. **Sem publicação automática** no YouTube ou em qualquer canal.
3. **Workflows só manuais** (`workflow_dispatch`), `concurrency`, `timeout-minutes ≤ 20`,
   `permissions: contents: read`, artifacts com retenção ≤ 3 dias. Testes conferem isso.
4. **Repositório da Reforma é somente leitura** e nada dele além do código autorizado pode
   entrar aqui (arte, fontes, imagens, áudio, kit, storyboard). `tests/test_repo_rules.py` confere.
5. **Nunca inventar** fontes, números, citações, imagens ou resultados. Toda afirmação do
   roteiro leva `[F:id]` apontando para `fontes.yaml`. Distinguir preliminar de consolidado.
6. **Toda imagem tem proveniência e licença verificadas** em `PROVENANCE.yaml`. Imagem na
   internet não é imagem liberada. Ilustração que possa parecer evidência leva rótulo.
7. **QA automático não é aprovação.** Nunca declarar vídeo, voz ou cena aprovados sem
   avaliação humana registrada (`docs/qa/CHECKLIST_HUMANO.md`).
8. **Parar nos pontos de aprovação** de cada fase (ver `docs/fase0-auditoria.md`).
9. Nunca versionar MP4/WAV, segredos ou chaves.

## Motor
- Coordenadas de projeto 1920×1080; saída em 720p (prévia) ou 1080p (entrega); 360p só em testes.
- Cores e fontes por nome, definidas em `brand/theme.yaml` (cores medidas na logo).
- Camadas: `text`, `picture`, `highlight`, `map`, `logo`, `fill`. Transições no
  `episode.yaml`: `crossfade`, `wipe`, `fade`.
- Cache por cena: só cenas alteradas (ou vizinhas de transição) são renderizadas de novo.
- Movimento lento de câmera sobre imagens: **permitido, não prioritário** (ainda não implementado).

## Verificação obrigatória antes de entregar
1. `python -m pytest -q`
2. Render real + `python -m qa.run …` sem falhas.
3. Olhar a folha de contato e os quadros; descrever limitações honestamente em `docs/qa/`.
4. Trabalhar em branch própria; nunca enviar direto para `main`.
