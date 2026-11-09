"""Render the wallet scene to MP4: frames (parallel, Skia) -> ffmpeg, plus audio and subtitles."""
import os, sys, subprocess, wave, multiprocessing as mp
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.audio import speech, build_mix, SR
from engine.lipsync import LipSync
from scenes import wallet_scene as S

LINE = "আরে! এখানে মানিব্যাগটা কার পড়ে আছে?"
OUT = os.environ.get("OUT_DIR", "output")
_ls = None

def _init():
    global _ls
    a, sr, ph = speech(LINE)
    _ls = LipSync(ph, a, sr, S.SPEECH_START)

def _frame(i):
    img = S.render_frame(i / S.FPS, _ls)
    return img.toarray(colorType=__import__("skia").kRGBA_8888_ColorType)[:, :, :3].tobytes()

def main():
    os.makedirs(OUT, exist_ok=True)
    only = [float(x) for x in sys.argv[1:]]
    if only:  # preview stills
        _init()
        for t in only:
            S.render_frame(t, _ls).save(f"{OUT}/still_{t:05.2f}.png")
        return
    a, sr, ph = speech(LINE)
    steps = [tl for tl, _ in S.PLAN_NEAR + S.PLAN_FAR]
    mix = build_mix(S.DURATION, a, sr, S.SPEECH_START, steps, {"rustle": [(6.3, 0.6), (7.2, 0.6)], "chime": [3.35]})
    with wave.open(f"{OUT}/audio.wav", "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    with open(f"{OUT}/subs.ass", "w") as f:
        f.write("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n[V4+ Styles]\n"
                "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Outline, Shadow, Alignment, MarginV\n"
                "Style: D,Noto Sans Bengali,54,&H00FFFFFF,&H00101010,&H80000000,1,3,1,2,70\n\n[Events]\n"
                "Format: Layer, Start, End, Style, Text\n"
                f"Dialogue: 0,0:00:{S.SPEECH_START:05.2f},0:00:11.85,D,{{\\fad(150,250)}}{LINE}\n")
    n = int(S.DURATION * S.FPS)
    raw = f"{OUT}/_video.mp4"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1920x1080",
                           "-r", str(S.FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                           "-pix_fmt", "yuv420p", raw], stdin=subprocess.PIPE)
    with mp.Pool(os.cpu_count(), initializer=_init) as pool:
        for k, buf in enumerate(pool.imap(_frame, range(n), chunksize=2)):
            ff.stdin.write(buf)
            if k % 24 == 0:
                print(f"frame {k}/{n}", flush=True)
    ff.stdin.close(); ff.wait()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-i", f"{OUT}/audio.wav", "-vf", f"ass={OUT}/subs.ass",
                    "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", "-shortest", f"{OUT}/wallet_scene_12s.mp4"], check=True)
    os.remove(raw)
    print("done")

if __name__ == "__main__":
    main()
