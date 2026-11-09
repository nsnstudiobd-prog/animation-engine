"""Timing primitives: easing curves, keyframe tracks, smooth noise."""
import math

def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x

def lerp(a, b, t):
    return a + (b - a) * t

def smoothstep(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0)) if e1 != e0 else (1.0 if x >= e1 else 0.0)
    return t * t * (3 - 2 * t)

def ease_in_out(t):   # cubic
    t = clamp(t)
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2

def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3

def ease_in(t):
    t = clamp(t)
    return t * t * t

def ease_out_back(t, s=1.6):
    t = clamp(t) - 1
    return t * t * ((s + 1) * t + s) + 1

def ease_quint(t):
    t = clamp(t)
    return 16 * t ** 5 if t < 0.5 else 1 - (-2 * t + 2) ** 5 / 2

def linear(t):
    return clamp(t)

EASE = {"io": ease_in_out, "out": ease_out, "in": ease_in, "back": ease_out_back,
        "lin": linear, "quint": ease_quint, "hold": lambda t: 0.0}


class Track:
    """Keyframe track. keys: [(time, value, ease_into_this_key)]. Values may be
    floats or tuples."""
    def __init__(self, keys):
        self.keys = sorted(keys, key=lambda k: k[0])

    def __call__(self, t):
        ks = self.keys
        if t <= ks[0][0]:
            return ks[0][1]
        if t >= ks[-1][0]:
            return ks[-1][1]
        for i in range(1, len(ks)):
            if t <= ks[i][0]:
                t0, v0 = ks[i - 1][0], ks[i - 1][1]
                t1, v1 = ks[i][0], ks[i][1]
                e = ks[i][2] if len(ks[i]) > 2 else "io"
                u = EASE[e]((t - t0) / (t1 - t0))
                if isinstance(v0, tuple):
                    return tuple(lerp(a, b, u) for a, b in zip(v0, v1))
                return lerp(v0, v1, u)
        return ks[-1][1]


def _hash(i, seed):
    n = (i * 374761393 + seed * 668265263) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0 * 2 - 1

def noise(x, seed=0):
    """Smooth 1D value noise in [-1, 1]."""
    i = math.floor(x)
    f = x - i
    u = f * f * (3 - 2 * f)
    return lerp(_hash(i, seed), _hash(i + 1, seed), u)

def fbm(x, seed=0, octaves=3):
    v, a, s = 0.0, 0.5, 1.0
    for o in range(octaves):
        v += a * noise(x * s, seed + o * 31)
        a *= 0.5
        s *= 2.0
    return v
