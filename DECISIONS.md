# DECISIONS.md

Formato: data · decisão · motivo · consequência.

**D01 · 2026-10-29 · Monólito FastAPI + React/Vite.** Pasta vazia, stack preferida no briefing.
Um processo de backend, SPA servido pelo próprio FastAPI após `npm run build`.

**D02 · 2026-10-29 · SQLite com tabela genérica de documentos (`records`).** Modelos Pydantic
serializados em JSON reduzem migrações no MVP. Consulta filtrada em Python; aceitável para volumes
locais (< 100 mil registros). Rever se houver consultas analíticas pesadas.

**D03 · 2026-10-29 · FFmpeg via `imageio-ffmpeg`.** FFmpeg não está instalado e instalação global
altera o sistema. O pacote traz binário local ao venv. `FFMPEG_PATH` permite usar outro binário.
Sem ffprobe: metadados lidos de `ffmpeg -i`.

**D04 · 2026-10-29 · Demanda via Wikimedia Pageviews.** Única fonte pública, gratuita, documentada e
sem chave disponível agora. Mede interesse por tema (enciclopédia), não buscas no YouTube — limitação
exibida no relatório. YouTube Data API entra como provedor opcional quando houver `YOUTUBE_API_KEY`.
Google Trends não tem API pública aberta; bibliotecas não oficiais foram descartadas (instáveis e
fora dos termos).

**D05 · 2026-10-29 · Critérios sem dado observado viram hipóteses explícitas em `config/niches.json`.**
O proprietário pode editá-las. A nota exibe cobertura e confiança; CPM/RPM nunca são estimados
numericamente.

**D06 · 2026-10-29 · Narração por Windows SAPI.** Vozes pt-BR (Maria) e en-US (Zira) instaladas, sem
custo. Qualidade robótica: adequada para teste técnico, não para publicação. Provedor substituível.

**D07 · 2026-10-29 · Roteiro por provedor `template` local.** Não há chave de LLM configurada. Gera
rascunho estruturado a partir de fatos com fonte. A verificação de originalidade (sobreposição de
n-gramas com as fontes) sinaliza trechos derivados; aprovação editorial humana é obrigatória.

**D08 · 2026-10-29 · Visuais gerados com Pillow e trilha sintetizada.** Garante direitos próprios
documentados no manifesto de cada vídeo, sem baixar material de terceiros.

**D10 · 2026-10-29 · Decisões do proprietário.** (1) Canal em **português do Brasil**: mercado
primário `pt`; inglês mantido apenas como comparação no relatório. (2) Modelo de produção **híbrido**:
local por padrão, LLM opcional para roteiros com teto de custo por execução (`max_cost_usd_per_run`).
(3) Estratégia: **Shorts criativos, cômicos e educativos**, roteiro dinâmico com estrutura de
**loop** (a frase final se conecta ao gancho para incentivar a revisualização natural). O loop não
pode esconder a resposta nem criar suspense não resolvido: a informação prometida é entregue antes
do fechamento. Vídeos longos ficam como etapa posterior, para temas validados pelos Shorts.

**D11 · 2026-10-30 · Dois canais (config/channels.json).** "Clip+" (histórias de reality de
restaurante, SOS Restaurante) e "Clip+ Nat" (ciência e curiosidades da natureza). Nomes definidos pelo proprietário em 2026-10-30.
Cada canal tem paleta, ícone, hashtags e identidade visual própria gerada localmente. Vídeos sempre
legendados (legenda embutida + SRT). "Melhores momentos" é feito por **recontagem narrada com visuais
originais**: cenas do programa só com licença registrada (Content ID e política de conteúdo reutilizado).
Edição externa (CapCut) é manual a partir da pasta `editavel/`; não há API oficial para automatizar.

**D12 · 2026-10-30 · Revisão humana com pré-visualização.** A aprovação final exige assistir ao vídeo
(≥ 90%) na própria tela de aprovação. "Editar e refazer" destrava o roteiro e repete revisão,
aprovação editorial e renderização. Cada alerta de qualidade aponta o campo exato (`field`).

**D13 · 2026-10-30 · Regra permanente "Visual First".** O vídeo precisa MOSTRAR o que é narrado. Agente
Visual Hunter busca filmagens reais por API oficial (Wikimedia Commons sem chave; Pexels/Pixabay com chave),
avalia licença (CC0/PD/CC BY aceitas; CC BY-SA condicional; NC/ND/desconhecida rejeitadas), baixa, amostra
quadros e propõe o material por cena. A correspondência automática usa só metadados; a confirmação visual é
humana (não há modelo de visão local). Ação sem filmagem adequada = cena pendente, nunca imagem genérica.
O QA bloqueia vídeos com cobertura visual validada < 100% em canais `require_footage` (Clip+ Nat).
Narração com marcas de tempo por palavra (SAPI SpeakProgress, corrigido de 16 kHz para a taxa real e
conferido pela energia do áudio). Trilha de suspense e efeitos são sintetizados localmente (sem API oficial
da YouTube Audio Library/Pixabay Music); ducking por sidechain e loudnorm -14 LUFS.

**D14 · 2026-10-30 · Pasta `imagens/`.** Cada geração de identidade visual é copiada para
`imagens/<canal>/` a pedido do proprietário; incluída nas pastas de escrita permitidas.

**D09 · 2026-10-29 · Publicação desativada.** Apenas pacote local. Upload exigirá OAuth oficial,
escopo `youtube.upload` mínimo e aprovação humana registrada.

**D15 · 2026-10-29 · Limpeza de reprovados.** Projeto encerrado sem aprovação final (reprovado, cancelado
tem vídeo e pacote apagados de `output/`. Falhas não são limpas (podem ser repetidas). Filmagens só são apagadas
quando o roteiro é reprovado, pois vídeo reprovado costuma ser refeito com o mesmo roteiro.

**D16 · 2026-10-29 · Abertura GeoZoom.** Shorts de natureza/animais começam com zoom do espaço até o país ou
região onde o tema ocorre (pedido do proprietário). O proprietário autorizou o GeoZoom (Node + Chrome local,
imagens NASA de domínio público). Escala de cidade fica borrada: cortar o zoom na escala regional.
