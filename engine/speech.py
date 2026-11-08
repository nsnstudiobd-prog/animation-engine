"""Bengali speech synthesis with exact phoneme timing (espeak-ng via ctypes).

Returns PCM audio plus a list of (start_sec, end_sec, phoneme) events which the
lip-sync module converts into visemes.
"""
import ctypes, ctypes.util
import numpy as np

class _ID(ctypes.Union):
    _fields_ = [("number", ctypes.c_int), ("name", ctypes.c_char_p), ("string", ctypes.c_char * 8)]

class _Event(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("unique_identifier", ctypes.c_uint),
                ("text_position", ctypes.c_int), ("length", ctypes.c_int),
                ("audio_position", ctypes.c_int), ("sample", ctypes.c_int),
                ("user_data", ctypes.c_void_p), ("id", _ID)]

_CB = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.POINTER(_Event))


def synthesize(text, voice="bn+m3", rate=135, pitch=42, prange=60):
    lib = ctypes.CDLL("libespeak-ng.so.1")
    sr = lib.espeak_Initialize(2, 0, None, 1)  # synchronous, phoneme events
    lib.espeak_SetVoiceByName(voice.encode())
    lib.espeak_SetParameter(1, rate, 0)    # rate
    lib.espeak_SetParameter(3, pitch, 0)   # pitch
    lib.espeak_SetParameter(4, prange, 0)  # range
    chunks, events = [], []

    def cb(wav, n, ev):
        if n > 0:
            chunks.append(np.ctypeslib.as_array(wav, shape=(n,)).copy())
        i = 0
        while ev[i].type != 0:
            e = ev[i]
            if e.type == 7:  # phoneme
                events.append((e.sample, e.id.string.decode("utf-8", "ignore")))
            elif e.type == 1:  # word
                events.append((e.sample, "#WORD"))
            i += 1
        return 0

    cbf = _CB(cb)
    lib.espeak_SetSynthCallback(cbf)
    b = text.encode("utf-8")
    lib.espeak_Synth(b, len(b) + 1, 0, 1, 0, 1, None, None)
    lib.espeak_Synchronize()
    audio = (np.concatenate(chunks).astype(np.float32) / 32768.0) if chunks else np.zeros(1, np.float32)
    phon = [(s / sr, p) for s, p in events if p != "#WORD"]
    out = []
    for k, (t, p) in enumerate(phon):
        t2 = phon[k + 1][0] if k + 1 < len(phon) else len(audio) / sr
        out.append((t, t2, p))
    return audio, sr, out
