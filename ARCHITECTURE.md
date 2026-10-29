# ARCHITECTURE.md

Monólito modular: um processo FastAPI + um SPA React. Sem microsserviços nem contêineres obrigatórios.

```
frontend/ (React + TS + Vite + Tailwind)  ──HTTP /api, /media──►  backend/app (FastAPI)
                                                                     │
   api/            rotas HTTP finas (validação Pydantic)             │
   orchestrator/   Orchestrator, Policy (somente leitura), runner     │
   agents/         8 agentes: contratos tipados, sem acesso a shell   │
   research/       provedores (Wikimedia, YouTube API, Trends), cache, scoring
   production/     TTS, visuais (Pillow), legendas, FFmpeg, pipeline
   integrations/   publicação (desativada), LLM (interface)          │
   store.py        SQLite (data/cios.db)                              │
config/  niches.json, scoring.json, policy.json   output/  vídeos, relatórios, pacotes
```

## Camadas e regras de dependência
- `api` → `orchestrator`, `store`, `research`, `models`. Nunca chama agentes diretamente para tarefas
  longas; cria tarefas no orquestrador.
- `orchestrator` → `agents`, `store`, `policy`. Único componente que muda estado de tarefas.
- `agents` → `research`, `production`, `integrations`. Recebem `AgentContext` (somente leitura da
  política, limites, logger) e devolvem `TaskResult`. Não escrevem no estado de outros agentes.
- `production` → subprocessos permitidos: `ffmpeg` e TTS local, com allowlist e timeout.

## Persistência
SQLite (`data/cios.db`), stdlib `sqlite3`:
- `records(kind, id, created_at, updated_at, data JSON)` — armazenamento de documentos Pydantic
  (tasks, workflows, niche_reports, trend_runs, briefs, scripts, jobs, quality_reports, metrics).
- `logs(ts, level, source, task_id, message)` — logs resumidos.
- `http_cache(key, fetched_at, ttl_s, body)` — cache de pesquisa.

## Provedores e substituição
| Interface | Implementação MVP | Alternativas previstas |
|-----------|-------------------|------------------------|
| `DemandProvider` | Wikimedia Pageviews (público, sem chave) | Google Trends (sem API oficial aberta) |
| `TrendProvider` | Wikimedia Top Articles | YouTube mostPopular (chave) |
| `CompetitionProvider` | YouTube Data API v3 (`YOUTUBE_API_KEY`), desativado sem chave | — |
| `ScriptProvider` | `template` (local, determinístico) | LLM (`ANTHROPIC_API_KEY`), não implementado |
| `TTSProvider` | Windows SAPI (System.Speech) | `silent` (fallback), serviços pagos |
| `MusicProvider` | Trilha sintetizada localmente (FFmpeg lavfi) — direitos próprios | biblioteca licenciada |
| `PublishProvider` | `disabled` — gera pacote local | YouTube Data API OAuth (upload) |

## Orquestração
- `Task` com `depends_on`; o runner (thread única + `ThreadPoolExecutor` limitado) executa tarefas
  prontas, respeitando `max_concurrency`, `max_tasks_per_run`, `task_timeout_s`, `max_retries`.
- Tarefas marcadas `requires_approval` param em `awaiting_approval`; só `POST /api/tasks/{id}/approve`
  (ação humana via UI) as libera.
- Orçamento: cada resultado informa `tokens_estimated` e `cost_estimated_usd`; o runner interrompe
  ao exceder `max_cost_usd_per_run`.

## FFmpeg
Resolução: `FFMPEG_PATH` → `ffmpeg` no PATH → binário do pacote `imageio-ffmpeg`. Duração/integridade
verificadas com o próprio `ffmpeg -i` (o pacote não inclui ffprobe).

## Saídas
`output/videos/<job_id>/` (mp4, srt, narração, manifesto de direitos), `output/reports/` (relatórios
de nichos em Markdown + JSON), `output/publish/<job_id>/` (pacote aguardando publicação manual).
