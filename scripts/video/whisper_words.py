"""Word timestamps of the author's voice files, for cutting shots and timing captions.

Usage (make_video.py runs it when its cache is missing):
  uv run --no-project --python 3.12 --with faster-whisper python -I whisper_words.py OUT.json
Model: faster-whisper small.en at D:/models/faster-whisper-small.en (or $WHISPER_MODEL), CPU,
int8, beam 5, no VAD. Runs locally; nothing leaves the machine. Audio is decoded with ffmpeg
(the bundled PyAV decoder fails on these files).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

VOICE = Path(__file__).resolve().parents[2] / "data/sources/video/voice"
ACTS = ["act1", "act2", "act3", "act4a1", "act4a2", "act4b", "act5b", "act6"]

model = WhisperModel(
    os.environ.get("WHISPER_MODEL", "D:/models/faster-whisper-small.en"),
    device="cpu",
    compute_type="int8",
)
out = {}
for act in ACTS:
    raw = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(VOICE / f"{act}.aac"),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "f32le",
            "-",
        ],
        capture_output=True,
        check=True,
    ).stdout
    segs, _ = model.transcribe(
        np.frombuffer(raw, np.float32), language="en", word_timestamps=True, beam_size=5
    )
    out[act] = [
        {"w": w.word, "s": round(w.start, 2), "e": round(w.end, 2)} for s in segs for w in s.words
    ]
    print(act, len(out[act]), "words", file=sys.stderr)
Path(sys.argv[1]).write_text(json.dumps(out, indent=0), encoding="utf-8")
