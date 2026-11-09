# animation-engine

Procedural 2D animation engine (Python + Skia vector rendering + ffmpeg).

**Test render:** `output/wallet_scene_12s.mp4`. It is 12 s, 1920×1080, 24 fps, H.264 video with AAC audio.

- `engine/character.py`: rigged character with IK legs/arms, pseudo-3D head turns, and a face rig (eyes, brows, blinks, visemes)
- `engine/speech.py` + `engine/lipsync.py`: Bengali TTS via espeak-ng with exact phoneme timing → viseme lip-sync
- `engine/audio.py`: voice processing, footsteps synced to the gait, ambience, music
- `scenes/wallet_scene.py`: environment layers, parallax/depth-of-field camera, timeline and acting
- `render.py`: parallel frame render → MP4 (`python3 render.py`, or `python3 render.py 3.7 9.3` for stills)

Requirements: `pip install skia-python numpy`, `apt install espeak-ng libegl1 fonts-noto-core`, ffmpeg with libass.
