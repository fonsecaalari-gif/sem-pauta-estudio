import math
import os
import random
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
FPS = 24
SR = 44100

_FONT_DIR = None
_font_cache = {}


def _font_dir():
    global _FONT_DIR
    if _FONT_DIR is None:
        import matplotlib
        _FONT_DIR = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
    return _FONT_DIR


def F(name, size):
    key = (name, size)
    if key not in _font_cache:
        path = os.path.join(_font_dir(), name)
        if not os.path.exists(path):
            path = os.path.join(_font_dir(), "DejaVuSans.ttf")
        _font_cache[key] = ImageFont.truetype(path, size)
    return _font_cache[key]


def tx(draw, x, y, text, font, color, anchor="lm"):
    draw.text((x, y), text, font=font, fill=color, anchor=anchor)


def P(X, Y, z):
    f = 600.0
    z = max(0.4, z)
    return (int(W / 2 + X * f / z), int(H / 2 - Y * f / z))


def _wrap_markup(text, font, max_w):
    words = text.split()
    lines, cur, cur_w = [], [], 0
    space_w = font.getbbox(" ")[2] if words else 0
    for w in words:
        plain = w.strip("*")
        wpx = font.getbbox(plain)[2]
        add = wpx + (space_w if cur else 0)
        if cur and cur_w + add > max_w:
            lines.append(cur)
            cur, cur_w = [w], wpx
        else:
            cur.append(w)
            cur_w += add
    if cur:
        lines.append(cur)
    return lines


def captions(img, t, caps, y=1540):
    active = None
    for (t0, t1, text) in caps:
        if t0 <= t <= t1 + 0.35:
            active = (t0, t1, text)
            break
    if active is None:
        return
    t0, t1, text = active
    a = min(1.0, max(0.0, min((t - t0) / 0.35, (t1 - t) / 0.35 + 1.0)))
    if a <= 0:
        return
    font = F("DejaVuSans-Bold.ttf", 46)
    lines = _wrap_markup(text, font, 900)
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    lh = 62
    total_h = len(lines) * lh
    box_h = total_h + 44
    by = y - box_h // 2
    d.rounded_rectangle([70, by, W - 70, by + box_h], radius=22, fill=(8, 10, 16, int(200 * a)))
    cy = by + 22 + lh // 2
    for line in lines:
        widths = [font.getbbox(wd.strip("*"))[2] for wd in line]
        sw = font.getbbox(" ")[2]
        total = sum(widths) + sw * (len(line) - 1)
        cx = (W - total) / 2
        for wd, wpx in zip(line, widths):
            col = (255, 90, 90, int(255 * a)) if wd.startswith("*") else (240, 240, 235, int(255 * a))
            d.text((cx, cy), wd.strip("*"), font=font, fill=col, anchor="lm")
            cx += wpx + sw
        cy += lh
    img.paste(Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB"), (0, 0))


def make_post(glitches, t_cut, window=18.0, chaos=1.0):
    glitches = list(glitches)

    def post(img, t):
        g = 0.0
        for gt in glitches:
            dt = abs(t - gt)
            if dt < 0.22:
                g = max(g, 1.0 - dt / 0.22)
        if t > t_cut:
            phase = ((t - t_cut) % 2.0) / 2.0
            g = max(g, 0.35 * math.sin(math.pi * phase) * chaos)
        if g <= 0.01:
            return img
        arr = np.array(img, dtype=np.int16)
        shift = int(14 * g * chaos)
        if shift > 0:
            arr[:, :, 0] = np.roll(arr[:, :, 0], shift, axis=1)
            arr[:, :, 2] = np.roll(arr[:, :, 2], -shift, axis=1)
        rng = random.Random(int(t * 997) ^ 0x5EED)
        nsl = int(6 * g) + 2
        for _ in range(nsl):
            y0 = rng.randrange(0, H - 40)
            hh = rng.randrange(6, 40)
            off = rng.randrange(-70, 70)
            arr[y0:y0 + hh] = np.roll(arr[y0:y0 + hh], off, axis=1)
        noise = (rng.random() * 60 * g)
        arr = arr + np.random.default_rng(int(t * 1000)).integers(-int(noise), int(noise) + 1, arr.shape, dtype=np.int16)
        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    return post


def endcard(title, subtitle, dt):
    fade = min(1.0, dt / 1.2)
    base = int(5 + 4 * fade)
    img = Image.new("RGB", (W, H), (base, base + 1, base + 4))
    draw = ImageDraw.Draw(img)
    f1 = F("DejaVuSans-Bold.ttf", 64)
    f2 = F("DejaVuSans-Bold.ttf", 40)
    c1 = tuple(int(c * fade) for c in (225, 228, 232))
    c2 = tuple(int(c * max(0.0, fade - 0.3) / 0.7) for c in (185, 75, 75))
    tx(draw, W // 2, H // 2 - 80, title, f1, c1, "mm")
    tx(draw, W // 2, H // 2 + 40, subtitle, f2, c2, "mm")
    v = 90
    vign = Image.new("L", (W, H), 0)
    dv = ImageDraw.Draw(vign)
    dv.ellipse([-W * 0.3, -H * 0.25, W * 1.3, H * 1.25], fill=255)
    vign = vign.filter(ImageFilter.GaussianBlur(220))
    black = Image.new("RGB", (W, H), (0, 0, 0))
    img = Image.composite(img, black, vign)
    return img, "RGB"


class Audio:
    def __init__(self, total, seed, t_cut=None):
        self.n = int(total * SR)
        self.buf = np.zeros(self.n, dtype=np.float64)
        self.rng = np.random.default_rng(seed)
        self.t_cut = t_cut

    def _t0n(self, t, dur):
        i0 = int(t * SR)
        n = int(dur * SR)
        if i0 >= self.n or n <= 0:
            return None, 0, None
        n = min(n, self.n - i0)
        return i0, n, np.arange(n) / SR

    def _add(self, t, sig, gain=1.0):
        i0 = int(t * SR)
        if i0 >= self.n:
            return
        n = min(len(sig), self.n - i0)
        self.buf[i0:i0 + n] += sig[:n] * gain

    def bed(self):
        t = np.arange(self.n) / SR
        drone = 0.05 * np.sin(2 * np.pi * 52 * t) + 0.035 * np.sin(2 * np.pi * 78 * t + 0.5)
        drone *= 1 + 0.25 * np.sin(2 * np.pi * 0.07 * t)
        hum = 0.012 * np.sin(2 * np.pi * 120 * t)
        hiss = 0.008 * self.rng.standard_normal(self.n)
        hiss = np.convolve(hiss, np.ones(8) / 8, mode="same")
        self.buf += drone + hum + hiss

    def creak(self, t, dur=1.2):
        i0, n, tt = self._t0n(t, dur)
        if n == 0:
            return
        f = 250 + 500 * tt / max(dur, 0.01)
        ph = 2 * np.pi * np.cumsum(f) / SR
        sig = np.sin(ph) * (0.5 + 0.5 * np.sin(2 * np.pi * 9 * tt))
        env = np.minimum(1, tt / 0.1) * np.exp(-2.5 * tt / dur)
        self._add(t, sig * env, 0.10)

    def step(self, t, nsteps=3, gap=0.5):
        for i in range(nsteps):
            self.hit(t + i * gap, f=55, dur=0.12, gain=0.25)

    def ding(self, t):
        for k in range(2):
            tt0 = t + k * 0.55
            i0, n, tt = self._t0n(tt0, 0.4)
            if n == 0:
                continue
            sig = (np.sin(2 * np.pi * 941 * tt) + 0.6 * np.sin(2 * np.pi * 1412 * tt))
            sig *= np.minimum(1, tt / 0.01) * np.exp(-6 * tt)
            self._add(tt0, sig, 0.14)

    def static(self, t, dur=0.4):
        i0, n, tt = self._t0n(t, dur)
        if n == 0:
            return
        noise = self.rng.standard_normal(n)
        noise = np.convolve(noise, np.array([1, -1.0]), mode="same")
        env = np.exp(-3 * tt / dur)
        self._add(t, noise * env, 0.16)

    def murmur(self, t, dur=4.0):
        i0, n, tt = self._t0n(t, dur)
        if n == 0:
            return
        rng = np.random.default_rng(int(t * 100) + 7)
        syl = np.clip(np.sin(2 * np.pi * 3.5 * tt + np.sin(2 * np.pi * 0.7 * tt)) , 0, 1) ** 1.5
        noise = rng.standard_normal(n)
        f = 180 + 120 * np.sin(2 * np.pi * 1.1 * tt)
        ph = 2 * np.pi * np.cumsum(f) / SR
        sig = np.sin(ph) * noise * 0.3
        sig = np.convolve(sig, np.ones(6) / 6, mode="same")
        self._add(t, sig * syl * 0.5, 0.16)

    def click(self, t):
        i0, n, tt = self._t0n(t, 0.03)
        if n == 0:
            return
        sig = self.rng.standard_normal(n) * np.exp(-tt * 800)
        self._add(t, sig, 0.25)

    def heart(self, t, dur, rate=70):
        period = 60.0 / rate
        k = 0
        while True:
            tt0 = t + k * period
            if tt0 > t + dur:
                break
            self.hit(tt0, f=48, dur=0.09, gain=0.30)
            self.hit(tt0 + 0.16, f=42, dur=0.08, gain=0.22)
            k += 1

    def hiss(self, t, dur=3.0):
        i0, n, tt = self._t0n(t, dur)
        if n == 0:
            return
        noise = self.rng.standard_normal(n)
        noise = np.convolve(noise, np.array([1.0, -1.0]), mode="same")
        env = np.minimum(1, tt / 0.4) * np.minimum(1, (dur - tt) / 0.6)
        self._add(t, noise * np.clip(env, 0, 1), 0.05)

    def hit(self, t, f=50, dur=0.5, gain=0.9):
        i0, n, tt = self._t0n(t, dur)
        if n == 0:
            return
        sig = np.sin(2 * np.pi * f * tt * (1 - 0.3 * tt / dur)) * np.exp(-5 * tt / dur)
        noise = self.rng.standard_normal(n) * np.exp(-18 * tt / dur) * 0.4
        self._add(t, sig + noise, gain * 0.35)

    def whoosh(self, t, dur=0.8):
        i0, n, tt = self._t0n(t, dur)
        if n == 0:
            return
        noise = self.rng.standard_normal(n)
        c = np.cumsum(noise)
        c -= np.linspace(c[0], c[-1], n)
        sig = c / (np.abs(c).max() + 1e-9)
        env = np.sin(np.pi * tt / dur) ** 2
        self._add(t, sig * env, 0.22)

    def tone(self, t, dur, freq=60):
        i0, n, tt = self._t0n(t, dur)
        if n == 0:
            return
        sig = np.sin(2 * np.pi * freq * tt) * np.minimum(1, tt / 0.8) * np.minimum(1, (dur - tt) / 1.0)
        self._add(t, sig, 0.16)

    def cut(self, t):
        i0 = int(t * SR)
        if i0 < self.n:
            ramp = int(0.05 * SR)
            self.buf[i0:] = 0
            if i0 + ramp < self.n:
                self.buf[i0:i0 + ramp] *= np.linspace(1, 0, ramp)

    def render(self):
        b = np.clip(self.buf, -0.95, 0.95)
        peak = np.abs(b).max()
        if peak > 0.95:
            b = b * 0.95 / peak
        return (b * 32767).astype(np.int16)


def _ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def main(mod, name):
    total = mod.TOTAL
    nframes = int(total * FPS)
    rng = random.Random(getattr(mod, "SEED", 0))
    post = getattr(mod, "post", None)

    exe = _ffmpeg_exe()
    tmp_vid = f"{name}_video.mp4"
    cmd = [exe, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
           "-crf", "22", "-pix_fmt", "yuv420p", tmp_vid]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for i in range(nframes):
        t = i / FPS
        res = mod.frame(t, rng)
        if isinstance(res, tuple):
            img = res[0]
        else:
            img = res
        if post is not None:
            img = post(img, t)
        proc.stdin.write(img.tobytes())
        if i % (FPS * 10) == 0:
            print(f"frame {i}/{nframes} (t={t:.1f}s)", flush=True)
    proc.stdin.close()
    proc.wait()

    A = mod.audio()
    data = A.render()
    wav_path = f"{name}_audio.wav"
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(data.tobytes())

    out = f"{name}.mp4"
    subprocess.run([exe, "-y", "-i", tmp_vid, "-i", wav_path, "-c:v", "copy",
                   "-c:a", "aac", "-b:a", "160k", "-shortest", out],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.remove(tmp_vid)
    os.remove(wav_path)
    print(f"OK: {out} ({total:.0f}s, {nframes} frames)")
