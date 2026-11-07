# Sem Pauta Estúdio

Gera os vídeos do canal **Sem Pauta** ([@somos.sempauta](https://youtube.com/@somos.sempauta)) sempre que você quiser:
a **Mistral** escolhe a pauta e escreve os roteiros a partir das notícias do dia, e o **kit do canal** (`kit/`) transforma
cada roteiro em vídeo, com narração, animações, vinheta 3D, legenda e thumbnail.

```
notícias (feeds RSS) → Mistral escolhe a pauta → Mistral escreve o roteiro → fotos licenciadas (Wikimedia Commons)
→ render (kit) → MP4 + título, descrição, hashtags, fontes → RELATORIO.md
```

## 1. Configurar (uma vez)
1. Repositório → **Settings → Secrets and variables → Actions → New repository secret**
   - Nome: `MISTRAL_API_KEY` · Valor: a sua chave da Mistral. **Nunca coloque a chave em nenhum arquivo do repositório.**
2. (Opcional) Na aba **Variables** do mesmo lugar: `MISTRAL_MODEL` para trocar o modelo (padrão `mistral-large-latest`).
3. (Opcional) Série de produto: preencha `kit/produtos/produto.md`. Enquanto tiver `TODO`, o vídeo de produto não é gerado.

## 2. Gerar vídeos
**Actions → Produzir vídeos → Run workflow** e escolha:

| Ação | O que sai |
|---|---|
| `hoje` | 3 Shorts + o vídeo longo do quadro do dia (+ Tutorial no domingo, + produto em dias alternados se houver link do viral) |
| `shorts` | Shorts (quantidade em "Quantos"); com "Tema", só sobre aquele tema |
| `longo` | o vídeo longo do quadro escolhido (ou do dia da semana) |
| `tutorial` | o Tutorial de Domingo (tema do banco `kit/templates/temas_tutorial.md` ou o que você escrever) |
| `produto` | Short "Sem Pauta Útil" a partir do link do post viral |

Marque **"Só gerar os roteiros"** para receber só os textos em segundos, sem renderizar.

Quando terminar (Shorts: ~10 min; produção do dia completa: ~40–60 min), abra a execução:
- o **resumo** mostra títulos, descrições, hashtags, fontes e o que conferir;
- em **Artifacts**, baixe `sem-pauta-N` (zip com os MP4, legendas `.srt`, thumbnails e `RELATORIO.md`). Fica disponível por 14 dias.

O histórico (`kit/history.json`) é salvo no repositório depois de cada execução, para a Mistral não repetir temas.

**Gerar sozinho todo dia:** em `.github/workflows/produzir.yml`, apague o `#` das linhas do `schedule`.

**Grade do vídeo longo:** Seg A Pauta da Semana · Ter Siga o Dinheiro · Qua Sem Pauta Explica · Qui Checagem da Semana ·
Sex Quem Votou (placar oficial da API da Câmara) · Sáb Linha do Tempo · Dom Resumo da Semana (+ Tutorial).

## 3. Rodar no seu computador (opcional)
Precisa de Python 3.10+ e ffmpeg.
```bash
pip install -r requirements.txt
python -m playwright install chromium          # para prints de páginas (documentos e tutoriais)
export MISTRAL_API_KEY="sua-chave"              # no Windows (PowerShell): $env:MISTRAL_API_KEY="sua-chave"
python -m estudio hoje                          # ou: shorts --tema "…" | longo --quadro siga_o_dinheiro | tutorial | produto --viral-url URL
```
Os vídeos saem em `saida/AAAA-MM-DD/`. Teste sem gastar a API: `ESTUDIO_LLM_FALSO=1 python -m estudio shorts --tts espeak`.

## 4. Antes de postar — sempre
- **Confira os números** (blocos de dado, gráfico e placar) na fonte. A Mistral recebe a instrução de usar só o que está nas
  fontes, e o programa confere o formato, mas IA ainda pode errar. O relatório lista o que conferir em cada vídeo.
- Veja o vídeo inteiro uma vez. Se algo estiver errado, edite o roteiro (`.json` no zip) e renderize de novo no seu computador:
  `cd kit && python3 scripts/render_short.py specs/<arquivo>.json --tts edge`.
- Longos: suba o `.srt` como legenda e configure a tela final. Produto: marque **"Inclui promoção paga"** no YouTube Studio.

## 5. Limites conhecidos
- **Fotos:** vêm do Wikimedia Commons com licença livre e crédito automático. Se não achar foto para um tema, o vídeo não é
  renderizado (regra do canal: nada de imagem genérica no lugar da pessoa). Às vezes a foto achada é de um contexto diferente: confira.
- **Documentos e tutoriais:** o programa tira print de páginas oficiais públicas. Telas que exigem login (app do FGTS, gov.br logado)
  ficam como pendência no relatório, e o tutorial só é renderizado quando os prints estiverem na pasta.
- **Viral da série de produto:** redes sociais costumam bloquear robôs; se o print falhar, rode `produto` no seu computador com
  `--viral-print print.png`.
- **Voz:** sintética (edge-tts). Para o vídeo longo, a voz humana é melhor para a monetização: grave e use o campo `audio` dos blocos.
- **Busca na web da Mistral** (`busca_web_mistral` em `estudio/config.json`): desligada por padrão; o Tutorial de Domingo depende dela.
- **Custo:** cada execução usa a API da Mistral (poucas dezenas de milhares de tokens por dia; veja os preços no painel da Mistral)
  e minutos do GitHub Actions (repositório privado: 2.000 min/mês grátis; a produção completa do dia gasta ~40–60).

## Estrutura
```
estudio/            o programa (Mistral, pauta, fotos, orquestração)
  prompts/          instruções que a Mistral recebe — edite aqui para ajustar tom e regras
  config.json       modelo, feeds de notícia, licenças aceitas, grade semanal
kit/                kit do canal: renderizadores, marca, moldes, referências, histórico
.github/workflows/  o botão "Run workflow"
```
