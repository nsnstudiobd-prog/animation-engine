"""Phoneme -> viseme lip-sync with coarticulation.

Each espeak-ng phoneme maps to a mouth target (open, wide, round, smile).
Targets are blended with Gaussian kernels centred on each phoneme so the
mouth flows between shapes; bilabials (m, b, p) get a strong weight so the
lips always close on them. The audio envelope gates the result so the mouth
rests during silence.
"""
import math
import numpy as np

VIS = {
    "a": (0.80, 0.35, 0.0, 0.05), "A": (0.85, 0.3, 0.0, 0.0), "&": (0.60, 0.65, 0.0, 0.1),
    "O": (0.62, 0.0, 0.55, 0.0), "o": (0.45, 0.0, 0.85, 0.0), "u": (0.22, 0.0, 1.0, 0.0),
    "e": (0.45, 0.75, 0.0, 0.2), "E": (0.55, 0.7, 0.0, 0.15), "i": (0.22, 0.95, 0.0, 0.35),
    "m": (0.0, 0.25, 0.0, 0.0), "b": (0.0, 0.2, 0.0, 0.0), "p": (0.0, 0.2, 0.0, 0.0),
    "f": (0.08, 0.4, 0.0, 0.0), "v": (0.08, 0.4, 0.0, 0.0),
    "*": (0.28, 0.4, 0.0, 0.0), "r": (0.25, 0.3, 0.2, 0.0), "r.": (0.25, 0.3, 0.15, 0.0),
    "t": (0.22, 0.55, 0.0, 0.0), "t.": (0.24, 0.5, 0.0, 0.0), "d": (0.22, 0.5, 0.0, 0.0),
    "n": (0.2, 0.5, 0.0, 0.0), "l": (0.28, 0.5, 0.0, 0.0), "s": (0.14, 0.8, 0.0, 0.1),
    "k": (0.3, 0.4, 0.0, 0.0), "k#": (0.32, 0.4, 0.0, 0.0), "g": (0.3, 0.4, 0.0, 0.0),
    "tS": (0.2, 0.2, 0.55, 0.0), "tS#": (0.22, 0.2, 0.55, 0.0), "dZ": (0.2, 0.2, 0.55, 0.0),
    "S": (0.18, 0.2, 0.6, 0.0), "h": (0.4, 0.4, 0.0, 0.0), "j": (0.2, 0.8, 0.0, 0.1),
    "N": (0.25, 0.4, 0.0, 0.0),
}
REST = (0.0, 0.0, 0.0, 0.0)


class LipSync:
    def __init__(self, phonemes, audio, sr, start, lead=0.035):
        self.start = start
        self.lead = lead
        self.items = []
        for t0, t1, p in phonemes:
            if p.startswith("_") or t1 - t0 <= 0.001:
                continue
            key = p if p in VIS else p.rstrip("#:.")
            v = VIS.get(key, (0.25, 0.4, 0.0, 0.0))
            w = 4.0 if key in ("m", "b", "p") else 1.0
            self.items.append(((t0 + t1) / 2, max(0.03, (t1 - t0) * 0.45), v, w, t0, t1))
        # envelope (10 ms hop)
        hop = int(sr * 0.01)
        n = len(audio) // hop
        env = np.array([np.sqrt(np.mean(audio[i * hop:(i + 1) * hop] ** 2)) for i in range(n)])
        env = env / (env.max() + 1e-9)
        k = np.exp(-0.5 * (np.arange(-4, 5) / 2.0) ** 2); k /= k.sum()
        self.env = np.convolve(env, k, mode="same")
        self.hop_t = 0.01

    def envelope(self, ts):
        i = int(ts / self.hop_t)
        if i < 0 or i >= len(self.env):
            return 0.0
        return float(self.env[i])

    def __call__(self, t):
        ts = t - self.start + self.lead
        acc = np.zeros(4)
        wsum = 0.0
        for c, sig, v, w, t0, t1 in self.items:
            d = ts - c
            if abs(d) > 4 * sig + 0.05:
                continue
            g = w * math.exp(-0.5 * (d / sig) ** 2)
            acc += g * np.array(v)
            wsum += g
        if wsum < 1e-4:
            return REST
        rest_w = 0.08
        m = (acc + rest_w * np.array(REST)) / (wsum + rest_w)
        env = self.envelope(ts)
        gate = min(1.0, 0.25 + 1.4 * env) if wsum > 0.3 else min(1.0, wsum * 2)
        return (float(m[0] * gate), float(m[1]), float(m[2]), float(m[3]))
