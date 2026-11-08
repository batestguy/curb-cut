"""Record the default speaker's output (WASAPI loopback) to a WAV until STOP exists.

Usage: python -I loopback.py OUT.wav STOPFILE STARTFILE
Writes STARTFILE with the epoch milliseconds of the first captured frame.
"""

import sys
import time
import wave
from pathlib import Path

import numpy as np
import soundcard as sc

out, stop, startf = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
RATE = 48000
spk = sc.default_speaker()
mic = sc.get_microphone(id=str(spk.name), include_loopback=True)
with mic.recorder(samplerate=RATE, channels=2) as rec, wave.open(str(out), "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(RATE)
    first = True
    while not stop.exists():
        data = rec.record(numframes=RATE // 10)
        if first:
            startf.write_text(str(int(time.time() * 1000 - 1000 * len(data) / RATE)))
            first = False
        w.writeframes((np.clip(data, -1, 1) * 32767).astype("<i2").tobytes())
print("stopped")
