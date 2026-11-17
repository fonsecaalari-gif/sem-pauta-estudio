# Porteiro — 03:17 (curta animado)

Roteiro de terror ("O Porteiro do 1408") renderizado em MP4 vertical 9:16.

- `porteiro.mp4` — vídeo final: 2 min 14 s, 1080×1920, 24 fps, H.264 + AAC
- `porteiro.py` — roteiro/cenas/áudio (fonte da animação)
- `kit.py` — motor de render (frames, legendas, glitches, áudio sintetizado, encode via ffmpeg)
- `char_simple.py` — personagens vetoriais (porteiro e morador)

Para renderizar de novo:
```bash
pip install pillow numpy imageio-ffmpeg matplotlib
python3 porteiro.py   # gera porteiro.mp4
```
