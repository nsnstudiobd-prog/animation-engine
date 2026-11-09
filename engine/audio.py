"""Sound: Bengali voice (espeak-ng), synced footsteps, ambience, music pad."""
import numpy as np
from .speech import synthesize

SR = 48000

def speech(text, max_pause=0.30):
    a, sr, ph = synthesize(text)
    # trim long internal pauses so the line fits the shot
    out_a, out_ph, shift, cut_from = [], [], 0.0, 0
    for t0, t1, p in ph:
        if p == "_:" and 0 < t0 < len(a) / sr - 0.2 and t1 - t0 > max_pause:
            s0, s1 = int((t0 + max_pause) * sr), int(t1 * sr)
            out_a.append(a[cut_from:s0]); cut_from = s1
            out_ph.append((t0 - shift, t0 + max_pause - shift, p))
            shift += (t1 - t0) - max_pause
            continue
        out_ph.append((t0 - shift, t1 - shift, p))
    out_a.append(a[cut_from:])
    a = np.concatenate(out_a)
    return a, sr, out_ph

def _resample(x, sr):
    n = int(len(x) * SR / sr)
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)

def _lp(x, a):
    y = np.empty_like(x); acc = 0.0
    for i in range(len(x)):
        acc += a * (x[i] - acc); y[i] = acc
    return y

def _lp_fast(x, cutoff):
    # FFT brickwall-ish smooth lowpass
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / (1 + (f / cutoff) ** 4)
    return np.fft.irfft(X, len(x)).astype(np.float32)

def _hp_fast(x, cutoff):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 - 1 / (1 + (f / cutoff) ** 4)
    return np.fft.irfft(X, len(x)).astype(np.float32)

def _reverb(x, mix=0.18):
    rng = np.random.default_rng(3)
    n = int(0.45 * SR)
    ir = rng.normal(0, 1, n) * np.exp(-np.linspace(0, 7, n))
    ir[0] = 0
    wet = np.fft.irfft(np.fft.rfft(x, len(x) + n) * np.fft.rfft(ir, len(x) + n))[:len(x)]
    wet = wet / (np.abs(wet).max() + 1e-9) * np.abs(x).max()
    return (x * (1 - mix) + wet * mix).astype(np.float32)

def build_mix(duration, voice, voice_sr, voice_start, footsteps, events):
    N = int(duration * SR)
    rng = np.random.default_rng(1)
    t = np.arange(N) / SR
    mix = np.zeros((N, 2), np.float32)
    # ambience: street hum + distant traffic swell
    noise = rng.normal(0, 1, N).astype(np.float32)
    amb = _lp_fast(noise, 400) * 0.05 * (0.8 + 0.2 * np.sin(t * 0.7))
    mix += np.stack([amb, np.roll(amb, 900)], 1)
    # kettle simmer (bubbly band noise)
    sim = _hp_fast(_lp_fast(rng.normal(0, 1, N).astype(np.float32), 3000), 900)
    sim *= 0.012 * (0.6 + 0.4 * (rng.random(N // 2400 + 1).repeat(2400)[:N]))
    mix += np.stack([sim * 0.6, sim], 1)
    # crow / birds chirps
    for c in (1.2, 2.9, 6.6, 10.2):
        d = 0.09; n = int(d * SR); tt = np.arange(n) / SR
        ch = np.sin(2 * np.pi * (3200 - 9000 * tt) * tt) * np.sin(np.pi * tt / d) * 0.02
        i = int(c * SR); mix[i:i + n, 0] += ch; mix[i:i + n, 1] += ch * 0.5
    # rickshaw bell
    for c in (2.2, 9.8):
        n = int(1.2 * SR); tt = np.arange(n) / SR
        b = sum(np.sin(2 * np.pi * f * tt) * a for f, a in ((2400, 1), (3610, 0.5), (5200, 0.25))) * np.exp(-tt * 5) * 0.025
        b = b * (1 + 0.5 * np.sign(np.sin(2 * np.pi * 14 * tt)) * (tt < 0.25))
        i = int(c * SR); mix[i:i + n, 0] += b * 0.4; mix[i:i + n, 1] += b
    # footsteps (sandal slaps) synced to foot landings
    for ft in footsteps:
        if ft < 0 or ft > duration - 0.2:
            continue
        n = int(0.12 * SR); tt = np.arange(n) / SR
        s = _lp_fast(rng.normal(0, 1, n).astype(np.float32), 2500) * np.exp(-tt * 45) * 0.35
        s += np.sin(2 * np.pi * 90 * tt) * np.exp(-tt * 30) * 0.12
        i = int(ft * SR); mix[i:i + n] += s[:, None]
    # spoon clinks
    for c in np.arange(0.4, duration - 0.4, 1.26):
        n = int(0.3 * SR); tt = np.arange(n) / SR
        s = (np.sin(2 * np.pi * 4200 * tt) + 0.5 * np.sin(2 * np.pi * 6100 * tt)) * np.exp(-tt * 25) * 0.012
        i = int(c * SR); mix[i:i + n, 0] += s; mix[i:i + n, 1] += s * 0.7
    # cloth rustle when bending
    for c, d in events.get("rustle", []):
        n = int(d * SR); tt = np.arange(n) / SR
        s = _hp_fast(rng.normal(0, 1, n).astype(np.float32), 1500) * np.sin(np.pi * tt / d) * 0.03
        i = int(c * SR); mix[i:i + n] += s[:, None]
    # music: soft pad in a pentatonic (Sa Re Ga Pa Dha) + discovery chime
    base = 146.83
    pad = np.zeros(N, np.float32)
    for f in (base, base * 1.5, base * 2, base * 2.52):
        pad += np.sin(2 * np.pi * f * t + np.sin(t * 0.5)) * 0.012
    pad *= np.clip(t / 1.5, 0, 1) * np.clip((duration - t) / 0.8, 0, 1)
    mix += np.stack([pad, pad], 1)
    notes = [(0.6, 2), (1.6, 4), (2.6, 3), (3.4, 7)]
    scale = [1, 9 / 8, 5 / 4, 3 / 2, 5 / 3, 2, 9 / 4, 5 / 2]
    for c, k in notes:
        n = int(1.5 * SR); tt = np.arange(n) / SR
        f = base * 2 * scale[k]
        s = (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt)) * np.exp(-tt * 3) * 0.035
        i = int(c * SR); mix[i:i + n, 0] += s * 0.8; mix[i:i + n, 1] += s
    for c in events.get("chime", []):
        n = int(2.0 * SR); tt = np.arange(n) / SR
        s = sum(np.sin(2 * np.pi * f * tt) for f in (1174.7, 1568, 2349.3)) * np.exp(-tt * 2.5) * 0.02
        i = int(c * SR); mix[i:i + n] += s[:, None]
    # voice
    v = _resample(voice, voice_sr)
    v = _hp_fast(_lp_fast(v, 6500), 110)
    v = np.tanh(v * 1.6) / np.tanh(1.6)
    v = _reverb(v, 0.12) * 0.55
    i = int(voice_start * SR)
    n = min(len(v), N - i)
    mix[i:i + n] += v[:n, None]
    # duck music/ambience slightly is implicit; normalise
    mix /= max(1.0, np.abs(mix).max() / 0.95)
    return mix
