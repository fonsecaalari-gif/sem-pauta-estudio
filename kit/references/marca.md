# Sem Pauta — Brand Notes (v3 · "Folha Riscada")

**Canal:** https://youtube.com/@somos.sempauta · **Assinatura:** "Fora da pauta. Dentro do fato."

## Conceito
"Pauta" tem dois sentidos: a **agenda** que a grande mídia e o poder definem, e as **linhas de uma folha de caderno**.
O símbolo é uma **folha pautada cortada por um traço vermelho diagonal (14°)**: à esquerda do corte, as linhas da pauta;
à direita, a folha em branco — **sem pauta**. Tudo na marca sai dessa ideia: a vinheta 3D (a lâmina corta a folha e as
linhas caem), a transição entre cenas (faixa vermelha a 14°) e a barra de progresso dividida em blocos.

## Voz e posicionamento
- Jornalismo direto com leitura de esquerda assumida. **Fato e opinião ficam visualmente separados na tela** (bloco "leitura").
- Frases curtas, verbo forte. Sem palavrão, sem ofensa pessoal, sem adjetivo que a fonte não sustente.
- Todo vídeo termina com **uma** pergunta de comentário.
- Evite: "gente", "fala pessoal", "inscreva-se e ative o sininho", frase inteira em caixa-alta na narração.

## Paleta (use SÓ estas)
| Nome | Hex | Uso |
|---|---|---|
| Carvão | `#0E0D10` | fundos, texto sobre papel |
| Grafite | `#1F1E23` | fundo do bloco "dado" |
| Papel | `#EEE7D7` | texto claro, tarjas, fundo do bloco "leitura" |
| Corte | `#FF3A1F` | símbolo, etiquetas, transição, barra de progresso, destaque em manchete |
| Âmbar | `#FFC21A` | **só** a palavra ativa da legenda e destaques em rótulos/citações |
| Névoa | `#8E8C96` | créditos, linhas da pauta, apoio |
Proibido: degradê colorido, neon, azul/ciano, qualquer outra cor de destaque. Âmbar nunca em área grande.

## Tipografia (todas OFL, em `brand/fonts/`)
| Papel | Fonte | Uso |
|---|---|---|
| Display | **Big Shoulders Display Black/ExtraBold** | manchetes, números, logotipo — sempre CAIXA-ALTA |
| Texto | **Inter Black/ExtraBold/Bold** | legendas (Black 74 px), rótulos de dado, citações |
| Dossiê | **IBM Plex Mono SemiBold/Medium** | etiquetas, fichas (FATO · data · fonte), créditos |

## Formato "O CORTE" (Short 1080×1920, 30 fps, 35–55 s + vinheta 1,8 s)
| # | Bloco (`type`) | Tempo | Visual | Som |
|---|---|---|---|---|
| 1 | `gancho` | 0–4 s | foto + manchete gigante (Big Shoulders 168) subindo da máscara, 1 palavra em vermelho | batida grave |
| 2 | `fato` | 5–9 s | ficha de dossiê no topo + tarja papel com manchete; destaque = bloco vermelho | — |
| 3 | `dado` | 5–8 s | fundo grafite pautado, **número gigante contando**, traço vermelho, rótulo | tiques do contador + batida |
| 4 | `leitura` | 6–9 s | **fundo papel** (único bloco claro), foto em recorte P&B inclinado, selo "NOSSA LEITURA · OPINIÃO" | — |
| 5 | `outro_lado` | 5–8 s | foto em P&B, aspas vermelhas, citação em Inter | — |
| 6 | `pergunta` | 4–6 s | manchete-pergunta + selo "COMENTA AQUI ↓" pulsando | — |
| + | vinheta | 1,8 s | folha 3D cortada → SEM PAUTA | lâmina + acorde |
Blocos podem repetir (ex.: dois `fato`), mas a ordem gancho → … → pergunta é fixa, e **todo vídeo opinativo tem `leitura` e `outro_lado`**.

## Regras de layout
- **Área segura:** topo 190 px, base 400 px, esquerda 60 px, direita 150 px.
- **Selo** (símbolo + SEM PAUTA) fixo em x=60, y=120.
- **Barra de progresso segmentada** (um segmento por bloco) logo acima do crédito: mostra a estrutura do vídeo.
- **Crédito** sempre visível na base da área segura (Plex Mono 22 px, caixa-alta).
- **Legenda** palavra a palavra, até 3 palavras por vez, Inter Black 74 px caixa-alta, papel com contorno carvão; palavra ativa em âmbar
  (no bloco `leitura`: texto carvão, palavra ativa em vermelho). Entra com "pop" de mola.
- **Transição "corte"** (9 quadros): faixa vermelha a 14° varre a tela da esquerda para a direita, com som de lâmina.
- **Movimento:** entradas com mola (stiffness 180–320, damping 14–22), saídas com ease-in; nada de animação linear.
- Toda cena tem foto real, documento ou manchete citada (exceto o fundo do `dado`, que usa a foto desfocada).

## Som
- Narração TTS pt-BR com tempo exato por palavra (edge-tts `WordBoundary`) — ou WhisperX para narração gravada.
- Trilha: `brand/sfx/trilha_pulso_96bpm.ogg` (original, sintetizada — livre de direitos). Os cortes caem no beat (librosa).
- Ducking automático (sidechain) da trilha sob a voz; mix final normalizado a **−14 LUFS**, pico −1,5 dBTP.

## Arquivos
`brand/logo/`: `simbolo_1024.png`, `simbolo_transparente_1024.png`, `avatar_800.png`, `chip_sempauta.png`,
`wordmark_fundo_escuro.png`, `wordmark_fundo_claro.png`, `banner_youtube_2560x1440.png` ·
`brand/vinheta/vinheta_1080x1920.mp4` · `brand/sfx/*.wav` · `brand/3d/cena.html` (cena Three.js) · `brand/tokens.json`.
Regerar: `python3 scripts/make_sound.py` · `python3 scripts/make_brand_assets.py [--vinheta]` · 3D: `cd brand/3d && npm i && node render3d.mjs sting`.
