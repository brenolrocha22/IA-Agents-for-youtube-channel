# AGENTS.md — Regras permanentes de engenharia

Leia este arquivo antes de qualquer tarefa. Especificação em [SPEC.md](SPEC.md), arquitetura em
[ARCHITECTURE.md](ARCHITECTURE.md), fila de trabalho em [TASKS.md](TASKS.md), decisões em [DECISIONS.md](DECISIONS.md).

## Fluxo de trabalho
1. Pegue a próxima tarefa pendente em TASKS.md. Não reinicie tarefas concluídas.
2. Leia apenas os arquivos listados na tarefa. Não reexplore o repositório inteiro.
3. Altere somente os arquivos autorizados pela tarefa. Expandir escopo exige nova tarefa.
4. Rode testes direcionados (`pytest backend/tests/test_<modulo>.py`, `npm test -- <arquivo>`).
   Suíte completa apenas em marcos (fim de fase).
5. Atualize TASKS.md (estado + resumo de 1–3 linhas) ao concluir. Decisões novas vão para DECISIONS.md.
6. Nunca declare algo concluído sem ter executado a verificação correspondente.

## Segurança (inegociável)
- Nunca ler, pedir, armazenar ou registrar senhas, cookies, tokens de navegador ou sessões autenticadas.
- Segredos só via variáveis de ambiente (`.env`, fora do git). A API expõe apenas "configurado / ausente".
- Nenhum agente publica, torna público, gasta dinheiro, cria contas, aceita termos ou altera credenciais.
  Essas ações exigem aprovação humana explícita registrada pelo orquestrador.
- Agentes não executam comandos de shell arbitrários. Subprocessos permitidos: FFmpeg e o
  sintetizador de voz local, com argumentos montados pelo código e timeout obrigatório.
- Escrita em disco somente dentro de `data/`, `output/` e `imagens/` (cópias da identidade visual por canal,
  pedido do proprietário). Exclusões fora dessas pastas são proibidas.
- A política (`config/policy.json`) é somente leitura em tempo de execução. Nenhum agente nem o
  orquestrador podem alterá-la.

## Integridade de dados
- Nunca inventar CPM, RPM, receita, volume de buscas ou métricas. Sem dado → `desconhecido`.
- Toda evidência tem fonte, data de coleta e classificação: `observado`, `estimativa` ou `hipótese`.
- Dados sintéticos só no modo demonstração, sempre marcados `demo=true` e com aviso na interface.
- Não afirmar acesso a métricas privadas de concorrentes nem a retenção real de terceiros.
- Não prometer viralização ou ganhos.

## Conteúdo
- Roteiros originais. Não copiar roteiros, transcrições ou estruturas protegidas de outros criadores.
- Materiais visuais e sonoros: gerados localmente ou com licença documentada no manifesto de direitos.
- Não baixar nem reciclar vídeos de terceiros.

## Estilo de código
- Backend: Python 3.12, FastAPI, Pydantic v2, tipagem em todas as funções públicas.
- Frontend: React + TypeScript estrito + Tailwind. Texto da interface em português brasileiro.
- Toda integração externa implementa uma interface de provedor (`is_configured()`, erro claro quando ausente).
- Comentários só onde o "porquê" não é óbvio.
