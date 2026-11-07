# Checklist de qualidade — Sem Pauta v3 (marque tudo antes de entregar)

**Editorial**
- [ ] Gancho com fato forte nos 3 primeiros segundos.
- [ ] Todo fato tem fonte citada (ficha na tela + descrição).
- [ ] Opinião só no bloco `leitura` (fundo papel); fato nunca aparece com selo de opinião, e vice-versa.
- [ ] Bloco `outro_lado` presente em vídeo opinativo, com atribuição clara.
- [ ] O número do bloco `dado` está na fonte e foi arredondado como ela.
- [ ] Nenhum boato, print sem origem ou perfil anônimo tratado como fato.

**Imagem e áudio**
- [ ] Toda foto tem licença que permite uso e crédito (ver `fontes_de_imagem.md`).
- [ ] A foto mostra a pessoa/local/documento citado; nada de imagem genérica fingindo ser a pessoa.
- [ ] Zero trecho de TV/rádio/vídeo de terceiros; zero música com copyright (use a trilha do kit).
- [ ] Narração clara, nomes próprios corretos; legenda acompanha a voz palavra por palavra.
- [ ] Nenhuma voz ou rosto de político gerado por IA.

**Técnico**
- [ ] 1080×1920, 30 fps, H.264 + AAC, 35–55 s + vinheta.
- [ ] Loudness ≈ −14 LUFS (o script normaliza; confira com `ffmpeg -i out.mp4 -af ebur128 -f null -`).
- [ ] Selo, legenda, manchete e crédito dentro da área segura; nada coberto pela interface do Shorts.
- [ ] Destaques `*asterisco*` renderizados corretamente (sem asterisco aparecendo na tela).
- [ ] Conferidos 4 quadros (`--preview`): gancho, fato, leitura, pergunta.
- [ ] Arquivo `AAAA-MM-DD_NN_slug.mp4` + `.txt` com título/descrição/hashtags.
