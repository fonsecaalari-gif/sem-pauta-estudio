#!/usr/bin/env python3
"""
Gera o design de som da marca Sem Pauta v3 — 100% sintetizado por código (sem direitos autorais).

  python3 scripts/make_sound.py

Saída em brand/sfx/:
  corte.wav     whoosh + lâmina (transição "corte" entre cenas)
  impacto.wav   batida grave (entrada do gancho / número)
  tique.wav     clique curto (contador do bloco "dado")
  vinheta.wav   assinatura sonora da vinheta 3D (1,8 s, sincronizada com o corte no frame 17)
  trilha_pulso_96bpm.ogg   cama musical de 64 s, loopável, em lá menor
"""
import os, wave
import numpy as np
from brand import ROOT

SR = 48000
OUT = os.path.join(ROOT, "brand", "sfx")
rng = np.random.default_rng(7)

def save(name, x, stereo_width=0.0):
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1:
        # leve abertura estéreo por atraso (Haas) quando pedido
        d = int(SR * 0.012 * stereo_width)
        l = x; r = np.concatenate([np.zeros(d), x[:len(x) - d]]) if d else x
        x = np.stack([l, r], 1)
    peak = np.max(np.abs(x)) or 1
    x = x / peak * 0.89
    with wave.open(os.path.join(OUT, name), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())
    print("ok", name, f"{len(x) / SR:.2f}s")

def t_(dur): return np.arange(int(SR * dur)) / SR

def onepole_lp(x, fc):
    """Passa-baixa de 1 polo com corte variável (fc pode ser array)."""
    fc = np.broadcast_to(fc, x.shape)
    a = np.exp(-2 * np.pi * fc / SR); y = np.empty_like(x); s = 0.0
    for i in range(len(x)): s = (1 - a[i]) * x[i] + a[i] * s; y[i] = s
    return y

def env(n, a, d, curve=3.0):
    """Envelope ataque/decay em amostras."""
    e = np.ones(n); ai = int(a * SR)
    if ai: e[:ai] = np.linspace(0, 1, ai)
    tail = np.arange(n - ai) / SR
    e[ai:] = np.exp(-tail * curve / max(d, 1e-3))
    return e

# ------------------------------------------------------------- efeitos
def whoosh(dur=0.42, up=True):
    t = t_(dur); n = len(t)
    noise = rng.standard_normal(n)
    u = t / dur
    fc = 300 + 7000 * (u ** 1.5 if up else (1 - u) ** 1.5)
    x = onepole_lp(noise, fc) - onepole_lp(noise, fc * 0.25)
    shape = np.sin(np.pi * np.clip(u, 0, 1)) ** 1.6
    return x * shape

def blade(dur=0.25):
    t = t_(dur)
    tone = np.sin(2 * np.pi * (2400 * t + 1800 * t * t)) * 0.25 + np.sin(2 * np.pi * 5200 * t) * 0.08
    click = rng.standard_normal(len(t)) * np.exp(-t * 180)
    return (tone + click * 0.8) * env(len(t), 0.002, 0.18, 4)

def kick(dur=0.6, f0=120, f1=42):
    t = t_(dur)
    f = f1 + (f0 - f1) * np.exp(-t * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * 6.5)
    click = rng.standard_normal(len(t)) * np.exp(-t * 400) * 0.35
    return np.tanh((body + click) * 1.6)

def hat(dur=0.06):
    t = t_(dur); x = rng.standard_normal(len(t))
    x = x - onepole_lp(x, 7000)
    return x * np.exp(-t * 70)

def tick():
    t = t_(0.045)
    return (np.sin(2 * np.pi * 1850 * t) * 0.6 + rng.standard_normal(len(t)) * 0.25) * np.exp(-t * 140)

def mix_at(buf, x, at, gain=1.0):
    i = int(at * SR); j = min(len(buf), i + len(x)); buf[i:j] += x[:j - i] * gain

def corte():
    b = np.zeros(int(SR * 0.5))
    mix_at(b, whoosh(0.34), 0.0, 0.9)
    mix_at(b, blade(0.22), 0.26, 0.55)   # a lâmina "fecha" no frame ~8 do corte
    return b

def impacto():
    b = np.zeros(int(SR * 0.9))
    mix_at(b, kick(0.9, 140, 38), 0.0, 1.0)
    sub = np.sin(2 * np.pi * 41 * t_(0.9)) * np.exp(-t_(0.9) * 3.2)
    mix_at(b, sub, 0.0, 0.5)
    mix_at(b, whoosh(0.18, up=False), 0.0, 0.25)
    return b

def chord(dur, freqs, decay=1.6):
    t = t_(dur); x = np.zeros(len(t))
    for k, f in enumerate(freqs):
        for h, g in ((1, 1), (2, .35), (3, .15)):
            x += g * np.sin(2 * np.pi * f * h * t + k) * (1 + 0.003 * np.sin(2 * np.pi * 5 * t))
    return x * env(len(t), 0.01, decay, 3)

def vinheta():
    # 1,8 s: entrada (0–0,45) → corte em 0,57 s (frame 17) → queda das linhas → acorde final
    b = np.zeros(int(SR * 1.8))
    mix_at(b, whoosh(0.55), 0.02, 0.6)
    mix_at(b, blade(0.25), 0.50, 0.9)
    mix_at(b, impacto(), 0.56, 0.9)
    paper = rng.standard_normal(int(SR * 0.9)); paper = (paper - onepole_lp(paper, 2500)) * np.exp(-t_(0.9) * 4) * (0.5 + 0.5 * np.sin(2 * np.pi * 23 * t_(0.9)) ** 2)
    mix_at(b, paper, 0.62, 0.25)
    mix_at(b, chord(1.2, [220.0, 261.63, 329.63, 440.0], 1.1), 0.58, 0.18)  # lá menor
    return b

# ------------------------------------------------------------- trilha
def trilha(bpm=96, bars=26):
    beat = 60 / bpm; dur = bars * 4 * beat
    b = np.zeros(int(SR * dur) + SR)
    roots = [55.0, 55.0, 43.65, 49.0]   # lá – lá – fá – sol (graves)
    for bar in range(bars):
        r = roots[bar % 4]
        for q in range(4):
            t0 = (bar * 4 + q) * beat
            mix_at(b, kick(0.4, 110, 45), t0, 0.85 if q in (0, 2) else 0.55)
            mix_at(b, hat(), t0 + beat / 2, 0.22)
            if q in (1, 3): mix_at(b, hat(0.12), t0, 0.12)
            # baixo pulsante em colcheias
            for e in range(2):
                tt = t_(beat / 2 * 0.9)
                bass = np.tanh(2.2 * np.sin(2 * np.pi * r * tt)) * env(len(tt), 0.005, 0.25, 3)
                mix_at(b, bass, t0 + e * beat / 2, 0.35)
        # pad suave a cada compasso
        pad = chord(4 * beat, [r * 4, r * 4 * 1.189, r * 6], decay=4 * beat * 1.4)
        mix_at(b, onepole_lp(pad, 1800), bar * 4 * beat, 0.08)
    b = b[:int(SR * dur)]
    fade = int(SR * 0.05); b[:fade] *= np.linspace(0, 1, fade); b[-fade:] *= np.linspace(1, 0, fade)
    return b

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    save("corte.wav", corte(), 0.6)
    save("impacto.wav", impacto())
    save("tique.wav", tick())
    save("vinheta.wav", vinheta(), 0.8)
    save("trilha_pulso_96bpm.wav", trilha(), 0.5)
    import subprocess   # trilha em OGG (bem menor; librosa e ffmpeg leem direto)
    w = os.path.join(OUT, "trilha_pulso_96bpm.wav")
    subprocess.check_call(["ffmpeg", "-loglevel", "error", "-y", "-i", w, "-c:a", "libvorbis", "-q:a", "6", w[:-4] + ".ogg"]); os.remove(w)
