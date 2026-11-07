# Roteiro de vídeo longo — Sem Pauta (8–12 min, 1.300–1.600 palavras)

## Regra de ouro do tempo
- Narração a ~150 palavras/min → **1.300 palavras ≈ 8 min 40 s** já contando cartões de capítulo, vinheta e tela final.
- O renderizador avisa se o vídeo ficar abaixo de 8 min. **Não estique com enrolação**: acrescente um capítulo, um documento ou um gráfico.
- Troque de bloco a cada **20–45 s**. Nenhum bloco narrado passa de 60 s (quebre em dois: `fato` + `documento`, `fato` + `grafico`).

## Esqueleto fixo
| Parte | Blocos | Tempo | Regra |
|---|---|---|---|
| Gancho frio | `abertura` | 0:00–0:25 | O fato, número ou pergunta mais forte. Sem "olá", sem "hoje vamos falar". |
| Vinheta | `vinheta` | 1,8 s | Sempre logo depois do gancho. |
| Capítulos (3–5) | `capitulo` + 2–4 blocos | ~2 min cada | Título curto (≤ 4 palavras) que funcione como capítulo do YouTube. |
| Nossa leitura | `leitura` | 40–60 s | Só opinião, começando com "Na nossa leitura…". |
| Outro lado | `outro_lado` | 25–40 s | O melhor argumento contrário, atribuído. |
| Encerramento | `encerramento` | 15–20 s | Uma pergunta + o quadro de amanhã. |
| Tela final | `tela_final` | 15 s | Sem fala. Configure os elementos de tela final no YouTube Studio. |

## Os 8 quadros (moldes em `longos/modelos/`)
| Dia | Quadro | Molde | Blocos-chave | Dados |
|---|---|---|---|---|
| Seg | **A Pauta da Semana** | `1_segunda_pauta_da_semana.json` | 4 capítulos (um por decisão), `fato`, `dado`/`documento` | `dados_publicos.py agenda` |
| Ter | **Siga o Dinheiro** | `2_terca_siga_o_dinheiro.json` | `documento`, `grafico` linha e barras, `placar` | Portal da Transparência, Orçamento |
| Qua | **Sem Pauta Explica** | `3_quarta_sem_pauta_explica.json` | `documento` (a lei), `linha_do_tempo`, `checagem` do mito | Constituição, leis, regimentos |
| Qui | **Checagem da Semana** | `4_quinta_checagem_da_semana.json` | 5× (`capitulo` + `checagem` + prova) | fontes oficiais de cada frase |
| Sex | **Quem Votou** | `5_sexta_quem_votou.json` | `placar` com partidos, `grafico` barras | `dados_publicos.py placar <id>` |
| Sáb | **Linha do Tempo** | `6_sabado_linha_do_tempo.json` | `linha_do_tempo`, `grafico` linha histórico | IBGE/SIDRA, arquivos oficiais |
| Dom | **Resumo da Semana** | `7_domingo_resumo_da_semana.json` | 7× (`capitulo` + `fato`) + comentários do público | os vídeos da semana |
| Dom (2º) | **Tutorial de Domingo** | `8_domingo_tutorial.json` | `checklist`, 5–8× `passo` com print e destaque, `alerta` | site/app oficial do serviço (conferido na semana) |

## Escrita
- Frases ≤ 20 palavras. Um número por frase. Escreva como se fala ("cento e setenta e um"; "Supremo" em vez de "STF" se a voz tropeçar).
- A cada capítulo, **retome a pergunta do gancho** em uma frase ("e é aqui que a CPI encontra o limite").
- `pontos` aparecem em sequência durante a fala: escreva a narração na mesma ordem.
- `checagem`: leia a frase exata, diga o veredito nos primeiros 3 s do bloco (o carimbo entra em ~2 s) e prove com a fonte.
- `documento`: a imagem precisa ser o documento real (print do DOU, PL, relatório), com o trecho citado em `destaque` [x, y, largura, altura] em frações da imagem.

## Voz
Para monetização, prefira **voz humana** (grave bloco a bloco, um arquivo por bloco, em `audio/`).
O renderizador sincroniza as legendas com `--align whisperx`. Voz sintética: declare na descrição.
