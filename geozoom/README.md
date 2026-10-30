# GeoZoom Agent

Gera, por código, um vídeo vertical da Terra vista do espaço com aproximação cinematográfica até um país,
uma região ou coordenadas. Não exige Google Earth Studio, contas, chaves de API nem serviços pagos.

## Como funciona
1. **Destino** (`src/destinations.ts`): nome de país em pt/en/ISO (Natural Earth), região de `data/regions.json`
   ou coordenadas `"lat,lon"`. A caixa geográfica inclui ilhas próximas relevantes (ex.: Tasmânia) e ignora
   territórios ultramarinos distantes.
2. **Câmera** (`src/camera.ts`): função pura do tempo. Começa a 22 000 km (Terra inteira no quadro 9:16),
   desloca-se até o destino com suavização seno e aproxima em escala logarítmica com suavização cúbica.
   Olha sempre para baixo, com o norte para cima, e mantém o destino no centro. Os últimos 8% do vídeo ficam parados no destino.
3. **Render** (`src/render.ts` + `web/index.html`): Chrome sem janela (puppeteer-core, usando o navegador
   instalado) abre CesiumJS sem loop automático. Cada quadro é renderizado num tempo exato e só é
   capturado quando `globe.tilesLoaded` está verdadeiro. A altura final é calculada pelo próprio Cesium
   (`getRectangleCameraCoordinates`) com 15% de margem.
4. **Vídeo**: FFmpeg do projeto → MP4 H.264, yuv420p, 1080x1920, 30 fps (padrão 8 s).
5. **Validação** (`src/validate.ts`): arquivo, codec, resolução, FPS, duração, decodificação completa,
   quadros vazios (blackdetect), continuidade (SSIM entre quadros consecutivos), tiles carregados e geografia
   (o centro do último quadro precisa estar dentro do destino, e os 4 cantos da caixa visíveis).

## Fontes e licenças (aptas para vídeo monetizado)
| Recurso | Fonte | Licença |
|---|---|---|
| Imagens da Terra | NASA Blue Marble ("Whole world – land and oceans", via Wikimedia Commons) | Domínio público (NASA) — sem sugerir endosso da NASA |
| Países | Natural Earth 1:50m | Domínio público |
| Globo 3D | CesiumJS | Apache-2.0 (sem Cesium ion: nenhuma conta/token) |
| Automação | puppeteer-core + Chrome instalado | Apache-2.0 |
| Estrelas | Geradas pelo projeto | Obra própria |

Créditos ficam em `CREDITOS.txt` junto a cada vídeo.

## Instalação
```powershell
cd geozoom
npm install
..\backend\.venv\Scripts\python.exe tools\prepare_assets.py all   # baixe antes as fontes em data/source (ver abaixo)
```
Arquivos em `data/source/` (não versionados):
- `bluemarble_24000.jpg` — https://commons.wikimedia.org/wiki/File:Whole_world_-_land_and_oceans_12000.jpg
- `ne_50m_admin_0_countries.geojson` — https://github.com/nvkelso/natural-earth-vector (pasta geojson)

## Uso
```powershell
npm run render -- "Austrália"
npm run render -- "Brazil" --duration 10
npm run render -- "Amazônia" --margin 1.25
npm run render -- "-25.27, 133.77"
npm test
```
Saída: `output/geozoom/<destino>_<data>/` com `geozoom_<destino>.mp4`, `ultimo_quadro.jpg`, `CREDITOS.txt` e `relatorio.json`.
Variáveis opcionais: `CHROME_PATH` (navegador) e `FFMPEG_PATH`.

## Limitações
- A resolução máxima das imagens é de ~0,73 km/pixel (nível 4). Serve para países e continentes; para cidades ou
  bairros a imagem fica borrada. Exigiria imagens de maior resolução com licença compatível.
- Sem relevo 3D (terreno elipsoidal), o que não muda nada na escala de país ou continente.
- O globo não tem iluminação dia/noite (luz uniforme), para manter o visual limpo e determinístico.
- A renderização usa WebGL no Chrome sem janela; em máquinas sem GPU fica mais lenta, mas o resultado é o mesmo.
