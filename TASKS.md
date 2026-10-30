# TASKS.md

Estados: `[ ]` pendente · `[~]` em andamento · `[x]` concluída (verificada) · `[!]` bloqueada.
Formato: Objetivo · Arquivos · Dependências · Aceitação · Testes · Interromper se.

## Fase 0 — Inspeção
- [x] **T00 Inspeção do ambiente.** Pasta vazia. Node 24.21, npm 11.19, Python 3.12.10, Git 2.56,
  Docker 29.8. FFmpeg ausente (→ D03). Vozes SAPI pt-BR/en-US. Wikimedia API acessível.
  Riscos: sem chaves de API (YouTube, LLM); voz sintética robótica; Wikipedia ≠ demanda do YouTube.

## Fase 1 — Especificação
- [x] **T01 Documentos.** AGENTS, SPEC (com decisões definitivas §0 e Reality Kitchen §7),
  ARCHITECTURE, TASKS, DECISIONS (D01–D10), .env.example, docs/MONETIZATION.md.

## Fases 2, 4, 5, 6, 7, 8 — Backend
- [x] **T02 Backend base** (FastAPI, SQLite, contratos Pydantic). `GET /api/health` ok.
- [x] **T05/T06 Pesquisa + scoring**: Wikimedia pageviews/top/summary com cache e orçamento;
  YouTube Data API opcional; ranking explicável com cobertura, confiança e bloqueio por risco crítico.
- [x] **T08 Orquestrador**: estados, dependências, limites (tempo, tentativas, concorrência, tarefas,
  API, custo), aprovação humana, cancelamento em cascata, recuperação de órfãos após reinício.
- [x] **T09 Conteúdo**: briefing, roteiro de Short em loop (cômico/educativo/criativo), retenção,
  revisão factual com originalidade (6-gramas), edição manual com nova revisão.
- [x] **T10 Produção**: SAPI/silent TTS, legendas SRT, quadros Pillow, trilha sintetizada, FFmpeg 9:16 e 16:9.
- [x] **T11 Qualidade**: QA técnico (resolução, áudio, integridade, volume, legendas, direitos,
  duração ≤ 60s), bloqueio de aprovação, pacote de publicação manual (`output/publish/`).
- [x] **T12 Analytics**: import CSV do YouTube Studio, registro manual, demo identificado.
  Verificação: `pytest backend/tests` → 15 passed (inclui render real de Short).

- [x] **T03/T04 Frontend**: React 19 + TS + Vite + Tailwind 4; sidebar, 9 páginas, estados de
  carregamento/vazio/erro, API real. `npm run build` ok; Vitest 4/4. Servido pelo FastAPI em :8000.
- [x] **T14 Reality Kitchen Stories**: catálogo (Wikipedia pt "Pesadelo na Cozinha", 48 episódios;
  lista en de Kitchen Nightmares), dossiê com fatos por etapa/categoria, verificação, roteiro 45–60s,
  cenas originais, registro de materiais licenciados, bloqueio de render sem licença. `test_kitchen.py` 3/3.
- [x] **T07 Relatório de nichos real**: `output/reports/nichos_20261029_042750.md`; tendências pt/en (40 cada).
- [x] **T15 Shorts de demonstração** (voz SAPI): Buraco negro (50,5s) e Bar Amigo Giannotti (49,6s),
  QA sem falhas; aprovação final aguardando o proprietário. Correção: estimativa calibrada (2,3 palavras/s)
  e nova síntese automática mais rápida se o Short passar de 60s.
- [x] **T13 Validação integrada + README.** pytest 18/18, Vitest 4/4, build ok, app real em :8000.

- [x] **T19 Revisão visual antes da aprovação** (2026-10-30): player com legendas e capa na tela de
  aprovação; aprovação final liberada só após assistir; edição de título/descrição/narração; "Editar e
  refazer"; alertas de qualidade clicáveis que levam ao campo exato. Testes: pytest 20/20, Vitest 4/4.
- [x] **T20 Dois canais + identidade visual**: Clip+ e Clip+ Natureza (provisório), página Canais,
  avatar 800x800, banner 2560x1440 (área segura), modelo de capa; quadros e capa de cada vídeo na
  paleta do canal; pasta `editavel/` no pacote (CapCut). Correção: tom/nicho/canal agora chegam ao roteiro.
- [x] **T21 Fonte do S.O.S. Restaurante** = *Restaurant: Impossible* (Robert Irvine). Catálogo da
  Wikipedia en: 287 episódios (50 com resumo). Resumos em inglês ficam como referência (`language`) e
  nunca entram na narração pt-BR; fatos em português são adicionados pelo proprietário com fonte.
- [x] **T22 Redesign Clip+** (estilo `clip_reality` em `production/brand_clip.py`, despachado por
  `production/branding.py`): chapéu branco, fonte Anton (OFL, `assets/fonts/anton`), logo circular +
  SVG, banner dinâmico na área segura, capa com título autoajustável e destaque amarelo; cache por mtime.
  Clip+ Nat inalterado. pytest 24/24, Vitest 4/4.
- [x] **T23 Redesign Clip+ Nat** (estilo `nat_wild` em `production/brand_nat.py`, reaproveita helpers do
  brand_clip): símbolo folha-bússola, curvas de nível, cordilheiras; banner na área segura; 3 variações de
  capa (vida selvagem, curiosidades, cinematográfica) escolhidas pelo título; suporte a frame licenciado
  (`image`); SVG do logo. Gerar novamente ok (~40s). Testes de branding 9/9 com API.
- [~] **T24 Visual Hunter + produção documental** (D13): agente, provedores Commons/Pexels/Pixabay,
  licenças, plano visual por cena, painel "Narração → vídeo" com cobertura, validação/troca/busca/adaptação,
  timestamps reais do TTS, legendas ASS, trilha + efeitos + ducking, QA de cobertura/licenças/créditos/
  telas pretas. Short do polvo: 6/7 cenas com filmagem real validada; **cena 6 (tinta) pendente** —
  sem filmagem licenciada no Commons. Desbloqueio: PEXELS_API_KEY/PIXABAY_API_KEY ou aprovar adaptação.
- [x] **T25 Pasta `imagens/`** (D14): cópia automática da identidade de cada canal.
- [x] **T26 Limpeza de vídeos não aprovados** (D15): reprovar/cancelar apaga `output/videos|publish/<job>`,
  `output/footage/<script>` e o registro do job; a varredura também roda ao iniciar o servidor.
- [~] **T27 Abertura GeoZoom nos Shorts** (D16): `VisualPlan.intro_clip` substitui o visual da cena 1
  (clipe ajustado à duração do gancho). Austrália: zoom até Sydney (cortado em 4,3s, antes de borrar);
  render 58,6s aguardando aprovação final. Falta: gerar o GeoZoom automaticamente no pipeline (hoje manual).
- [x] **T28 Legenda duplicada com números**: marca de voz "5 animais" + "animais" → dedupe em `caption_chunks`.

## Próxima tarefa recomendada
- [ ] **T16 Provedor LLM (modo híbrido)** para reescrever fatos com originalidade e humor real, com teto
  de custo por execução. Requer decisão + `ANTHROPIC_API_KEY`. Até lá: reescrever roteiros manualmente.
- [ ] **T17 Classificação de etapas Kitchen**: priorizar "conflito" quando a frase cita problemas
  (hoje "chef" + "problemas" vira "intervenção").
- [ ] **T18 Visuais**: ícones/ilustrações originais por cena (hoje: cartões tipográficos).

## Backlog (não iniciar sem decisão do proprietário)
- Provedor LLM para roteiros (modo híbrido) com teto de custo — requer `ANTHROPIC_API_KEY`.
- OAuth YouTube (Analytics + upload) com escopos mínimos.
- Voz neural (provedor pago, com teto de gasto).
- Biblioteca de mídia licenciada (Pexels/Pixabay API) com registro de licença.
