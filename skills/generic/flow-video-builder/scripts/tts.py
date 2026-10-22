"""Narration with an offline voice (Piper). One WAV per scene plus audio/timing.json with the start time of every sentence.

    $FLOWVIDEO_HOME/venv/bin/python tts.py --project DIR

Scenes whose narration did not change keep their audio (cached by hash), so the recordings made against it stay in sync.
"""
import argparse
import hashlib
import json
import os
import wave

import numpy as np

HOME = os.environ.get("FLOWVIDEO_HOME", os.path.expanduser("~/.cache/flow-video-builder"))
GAP = 0.45  # seconds of silence between sentences

ap = argparse.ArgumentParser()
ap.add_argument("--project", default=".")
args = ap.parse_args()
PROJ = os.path.abspath(args.project)
flow = json.load(open(os.path.join(PROJ, "flow.json")))
cfg = flow.get("config", {})
AUDIO = os.path.join(PROJ, "audio")
os.makedirs(AUDIO, exist_ok=True)

from piper import PiperVoice, SynthesisConfig  # noqa: E402

voice_name = cfg.get("voice", "en_US-amy-medium")
model = os.path.join(HOME, "voices", voice_name + ".onnx")
if not os.path.exists(model):
    import subprocess
    import sys
    subprocess.run([sys.executable, "-m", "piper.download_voices", voice_name, "--data-dir", os.path.join(HOME, "voices")], check=True)
voice = PiperVoice.load(model)
syn = SynthesisConfig(length_scale=cfg.get("speed", 1.14), noise_scale=cfg.get("noise", 0.45), noise_w_scale=cfg.get("noise_w", 0.55), volume=cfg.get("volume", 0.9))

timing_path = os.path.join(AUDIO, "timing.json")
old = json.load(open(timing_path)) if os.path.exists(timing_path) else {}
timing = {}
for sc in flow["scenes"]:
    h = hashlib.md5(json.dumps([sc["narr"], voice_name, cfg.get("speed", 1.14)]).encode()).hexdigest()
    wav_path = os.path.join(AUDIO, sc["id"] + ".wav")
    if old.get(sc["id"], {}).get("hash") == h and os.path.exists(wav_path):
        timing[sc["id"]] = old[sc["id"]]
        print(sc["id"], "cached")
        continue
    rate = voice.config.sample_rate
    parts, starts, t = [], [], 0.0
    for sentence in sc["narr"]:
        audio = np.concatenate([c.audio_int16_array for c in voice.synthesize(sentence, syn_config=syn)])
        starts.append(round(t, 3))
        parts += [audio, np.zeros(int(rate * GAP), dtype=np.int16)]
        t += len(audio) / rate + GAP
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(np.concatenate(parts).tobytes())
    timing[sc["id"]] = {"hash": h, "starts": starts, "total": round(t, 3), "rate": rate}
    print(sc["id"], round(t, 1), "s")
json.dump(timing, open(timing_path, "w"), indent=1)
