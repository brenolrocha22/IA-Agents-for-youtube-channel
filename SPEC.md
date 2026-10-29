# SPEC.md — Creator Intelligence OS

Aplicação local (Windows 10) para pesquisa de nichos, planejamento, produção e controle de qualidade
de vídeos para YouTube, com aprovação humana obrigatória antes de qualquer publicação.

Conta pretendida para o canal: `adventuresextime@gmail.com` (não presumida autenticada; nenhuma
integração usa essa conta sem OAuth oficial consentido pelo proprietário).

## 0. Decisões definitivas do proprietário (2026-10-29)
- Produção em **português brasileiro**, público inicial **Brasil**; interface em pt-BR, tema escuro, visual de SaaS.
- Modelo **híbrido**: local por padrão; APIs externas só com configuração explícita.
- Formato prioritário: **YouTube Shorts verticais de até 60s** (`max_short_duration_s`); arquitetura aceita outras durações.
- Tom: Shorts criativos, cômicos e educativos, com roteiro dinâmico em **loop** honesto (D10).
- Objetivo: canal original, sustentável, com potencial de monetização (sem promessas).
- Ordem de comparação de nichos: (1) curiosidades/mistérios/storytelling, (2) IA e tecnologia,
  (3) psicologia, (4) finanças pessoais, (5) negócios, (6) ciência e espaço, (7) games e outros
  (inclui reality shows de cozinha). O nicho definitivo só é escolhido com evidências.
- Linha editorial adicional: **Reality Kitchen Stories** (§7).
- Nada é publicado automaticamente.

## 1. Requisitos funcionais

| ID | Requisito | Prioridade |
|----|-----------|-----------|
| RF01 | Dashboard com projetos, tarefas, vídeos, erros, custos estimados e últimas oportunidades | P0 |
| RF02 | Ranking de nichos 0–100 com critérios, pesos configuráveis, evidências, fontes, data e riscos | P1 |
| RF03 | Pesquisa por mercado: pt-BR e inglês (internacional quando houver evidência) | P1 |
| RF04 | Trend Explorer: assuntos emergentes, fontes, histórico de coletas, filtros por idioma/categoria | P1 |
| RF05 | Orquestrador com tarefas tipadas, dependências, estados, limites, logs e pontos de aprovação | P1 |
| RF06 | Briefing → roteiro original (longo e Short), títulos, descrição, ideias de thumbnail | P1 |
| RF07 | Revisão factual e editorial; edição manual do roteiro | P1 |
| RF08 | Produção local: narração (provedor configurável), visuais, legendas sincronizadas, trilha com direitos documentados, render 16:9 e 9:16 via FFmpeg | P2 |
| RF09 | Verificação técnica e de conformidade; bloqueio interno de aprovação | P2 |
| RF10 | Pacote de publicação preparado, nunca enviado sem aprovação e integração autorizada | P3 |
| RF11 | Registro e importação de métricas (CSV do YouTube Studio / manual); comparação por formato, tema, duração, gancho, título | P3 |
| RF12 | Modo demonstração de analytics claramente identificado | P3 |
| RF13 | Settings: provedores, variáveis (presença apenas), limites, permissões, produção | P0 |

## 2. Metodologia de pontuação de nichos (RF02)

Critérios (0–100 cada), pesos em `config/scoring.json`:

| Critério | Fonte no MVP | Classificação |
|----------|--------------|---------------|
| Demanda observável | Pageviews Wikimedia (90 dias) dos artigos-semente do nicho, por idioma | observado |
| Crescimento | Pageviews últimos 3 meses vs. 3 meses anteriores | observado |
| Concorrência / diferenciação | YouTube Data API se configurada; senão hipótese documentada | observado ou hipótese |
| Retenção potencial | Hipótese editorial documentada | hipótese |
| Monetização | Hipótese qualitativa (adequação a anunciantes, afiliados). **Nunca CPM inventado** | hipótese |
| Facilidade/custo de produção | Estimativa baseada nos recursos exigidos pela pipeline local | estimativa |
| Risco de conformidade (invertido) | Estimativa: direitos autorais, políticas sensíveis, conteúdo reutilizado | estimativa |

Regras:
- Critério `desconhecido` sai da média; pesos renormalizados; **cobertura** = soma dos pesos com dado.
- Cada nicho exibe **confiança** derivada da proporção de critérios observados.
- Riscos críticos geram alerta independente da nota e o nicho não pode aparecer como "recomendado".
- O relatório separa fatos, estimativas e hipóteses e lista fontes com data de coleta.

## 3. Fluxo de produção (RF05–RF10)

`research → brief → script → fact_review → [aprovação editorial] → narration → visuals → captions →
render → technical_qa → [aprovação final] → publish_prep`

Estados de tarefa: `pending, running, completed, failed, cancelled, awaiting_approval`.

## 4. Requisitos não funcionais

- RNF01: abre localmente sem serviço pago; `http://localhost:8000` (app) / `http://localhost:5173` (dev).
- RNF02: segredos nunca aparecem em logs, API ou frontend.
- RNF03: limites configuráveis — tempo por tarefa, tentativas, concorrência, tarefas por execução,
  tamanho de arquivo, chamadas de API por execução, custo estimado máximo.
- RNF04: sem loops infinitos ou processos órfãos (timeouts em subprocessos, threads encerradas no shutdown).
- RNF05: cache de pesquisa em SQLite com TTL.
- RNF06: interface em pt-BR, tema escuro, responsiva, com estados de carregamento, vazio, sucesso e erro.
- RNF07: testes essenciais com pytest e Vitest.

## 5. Fora de escopo do MVP
Upload real ao YouTube, OAuth, geração de imagens por IA, vozes pagas, AdSense/pagamentos,
microsserviços. Ver interfaces previstas em ARCHITECTURE.md e requisitos de monetização em
[docs/MONETIZATION.md](docs/MONETIZATION.md).

## 7. Reality Kitchen Stories (agente especializado)
Shorts narrativos (45–60s, pt-BR) sobre crises e transformações de restaurantes mostradas em
programas como *Kitchen Nightmares* / *Pesadelo na Cozinha* / *SOS Restaurante*.
- Pesquisa em fontes públicas (listas de episódios da Wikipedia + fontes adicionadas pelo proprietário).
- Dossiê por história com fatos classificados: `exibido_no_programa`, `declaracao`,
  `posterior_verificado`, `interpretacao_editorial`; cada fato com fonte e etapa narrativa
  (gancho, contexto, conflito, intervenção, transformação, resultado). Etapas sem fato ficam
  **ausentes** — nunca inventadas. Ano de exibição sempre citado (evita apresentar fato antigo como atual).
- Roteiro com título provisório, gancho, narração, cenas e recursos visuais, legendas, fontes,
  duração estimada, observações de direitos, verificação de fatos e estado da aprovação.
- Direitos: nenhuma cena de episódio é baixada ou extraída. Visuais originais (gráficos, linha do
  tempo, cartões). Material de terceiros só com registro de origem, licença, escopo e restrições;
  cenas que dependam de material não autorizado **bloqueiam a renderização**, e o agente oferece alternativa original.
- Dashboard: episódios pesquisados, restaurantes, roteiros, vídeos em produção, materiais
  autorizados, pendências de verificação, aprovações e vídeos concluídos.

## 6. Critérios de aceitação do MVP
Ver lista da seção 16 do briefing original; o acompanhamento está em TASKS.md (marco M9).
