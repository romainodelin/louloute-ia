"""Génère une petite musique d'ambiance dynamique, 100 % libre de droits (synthèse maison).
Usage : python outils/generer_beat.py  ->  reels/musique/beat-louloutre-<bpm>.mp3"""
import numpy as np, subprocess, shutil, os, sys
SR, BPM, MESURES = 44100, int(sys.argv[1]) if len(sys.argv) > 1 else 118, 16
b = 60 / BPM; N = int(SR * b * 4 * MESURES); out = np.zeros((N, 2))
rng = np.random.default_rng(7)
def add(sig, t, pan=0.0, g=1.0):
    i = int(t * SR); j = min(N, i + len(sig))
    if i < N: out[i:j, 0] += sig[:j-i] * g * (1 - pan); out[i:j, 1] += sig[:j-i] * g * (1 + pan)
def env(n, a=0.005, r=0.2):
    t = np.arange(n) / SR; return np.minimum(t / a, 1) * np.exp(-t / r)
def kick():
    t = np.arange(int(.35 * SR)) / SR; f = 50 + 90 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)
def hat(): n = int(.05 * SR); return rng.standard_normal(n) * env(n, .001, .015) * .25
def clap():
    n = int(.2 * SR); x = rng.standard_normal(n) * env(n, .002, .06)
    return np.convolve(x, [1, -1], "same") * .5
def note(freq, dur, kind="pluck"):
    n = int(dur * SR); t = np.arange(n) / SR
    if kind == "bass": s = np.sign(np.sin(2*np.pi*freq*t)) * .35 + np.sin(2*np.pi*freq*t) * .6; return s * env(n, .005, dur*.6) * .5
    s = sum(np.sin(2*np.pi*freq*k*t) / k**1.6 for k in range(1, 6))
    return s * env(n, .004, .25) * .18
hz = lambda m: 440 * 2 ** ((m - 69) / 12)
accords = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]   # Am F C G
motif = [0, 2, 1, 2, 0, 1, 2, 1]
for m in range(MESURES):
    t0 = m * 4 * b; ac = accords[m % 4]; intro = m < 2
    for k in range(4):
        if not intro: add(kick(), t0 + k*b, g=.9)
        if k in (1, 3) and not intro: add(clap(), t0 + k*b, g=.5)
        add(hat(), t0 + k*b + b/2, pan=.3)
        if m >= 4: add(hat(), t0 + k*b + b/4, pan=-.3, g=.5)
    for k in range(8):
        add(note(hz(ac[motif[k]] + 12), b/2), t0 + k*b/2, pan=(-.4 if k % 2 else .4))
    if not intro:
        for k in (0, 1.5, 2.5, 3):
            add(note(hz(ac[0] - 12), b*.45, "bass"), t0 + k*b)
out = out / np.max(np.abs(out)) * .85
fade = int(SR * 1.0); out[-fade:] *= np.linspace(1, 0, fade)[:, None]
os.makedirs(os.path.join(os.path.dirname(__file__), "..", "musique"), exist_ok=True)
wav = "/tmp/beat.wav"; import wave
with wave.open(wav, "w") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((out * 32767).astype("<i2").tobytes())
try: import imageio_ffmpeg; ff = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError: ff = shutil.which("ffmpeg")
dest = os.path.join(os.path.dirname(__file__), "..", "musique", f"beat-louloutre-{BPM}.mp3")
subprocess.run([ff, "-y", "-loglevel", "error", "-i", wav, "-b:a", "192k", dest], check=True)
print("OK", os.path.abspath(dest))
