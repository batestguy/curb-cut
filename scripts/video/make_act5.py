"""Cut act 5 from the NVDA recording: four scenes, lower-third cards, crossfades, -16 LUFS.

Usage: python -I scripts/video/make_act5.py  -> data/sources/video/clips/act5.mp4 (git-ignored)
Times come from speech.json (the recording's own step log); audio time = log time + offset.
"""

import glob
import json
import subprocess
from pathlib import Path

VID = Path(__file__).resolve().parents[2] / "data/sources/video"
HERE = VID / "rec"  # the recording: speech.json, video/, nvda.wav
CLIPS = VID / "clips"
CARDS = VID / "cards"
d = json.loads((HERE / "speech.json").read_text(encoding="utf-8"))
OFF = (d["videoStartEpoch"] - d["audioStartEpoch"]) / 1000
VIDEO = glob.glob(str(HERE / "video" / "*.webm"))[0]
steps = {(e["scene"], e["step"]): e for e in d["log"] if "start" in e and not e.get("skipped")}
s = lambda sc, st: steps[(sc, st)]["start"] / 1000  # noqa: E731
e_ = lambda sc, st: steps[(sc, st)]["end"] / 1000  # noqa: E731

# (scene, start, end, fade-out seconds) in log time; audio time = log time + OFF.
# Agreed with the author 2026-11-07 ("trim it"), about 1:35. Sentence edges from silencedetect
# on nvda.wav (audio seconds): "Dot plot: ..." starts 91.77; it ends 97.42; the "37 dots"
# sentence runs 98.35-103.92; the Lagos sentence ends 125.24. A scene's later pieces join
# with the same dissolve as scene changes, so no cut is hidden.
A = lambda t: t - OFF  # noqa: E731  audio seconds -> log seconds
# Edges checked against the speech envelope (0.1 s steps): NVDA's speech runs behind the log,
# so scene 3 starts after the previous line stops (C: speech from 123.0; Down 7: gap at
# 152.9-153.1),
# Lagos's "precision: reliable" ends at 163.9 (speech from 164.6 is the poverty page loading, so
# that piece holds its last frame from 162.6), and the poverty sentence ends about 196.2.
# (scene, start, end, fade-out seconds, last video second or None), log time.
# 2026-11-07, author: no state names spoken in the video. The chart scene keeps NVDA's
# opening ("Dot plot: ..." and "37 dots, one per state, ...") and fades out before "Highest
# estimate: <state>"; the keyboard scene (NVDA names the state it picks) is dropped.
SEGMENTS = [
    ("s1-main", s("s1-main", "Down 3") - 0.3, s("s1-main", "Down 6"), 0.2, None),
    ("s2-chart", A(91.77) - 0.25, A(103.92) + 0.45, 0.6, None),
    ("s4-poverty", s("s4-poverty", "H 2") - 0.3, 196.5, 0.6, None),
]
XF = 0.5  # crossfade seconds

parts = []
seen = set()
for k, (sc, t0, t1, fo, vend) in enumerate(SEGMENTS):
    dur = t1 - t0
    out = CLIPS / f"act5-{k}-{sc}.mp4"
    first = sc not in seen
    seen.add(sc)
    over = (
        "[2:v]format=rgba,fade=in:st=0.3:d=0.4:alpha=1,fade=out:st=5.4:d=0.4:alpha=1[c];"
        "[0:v]fps=30,format=yuv420p[v0];[v0][c]overlay=eof_action=pass:format=auto,format=yuv420p[v];"
        if first
        else "[0:v]fps=30,format=yuv420p[v];"
    )
    vdur = (vend - t0) if vend else dur
    if vend:  # hold the last frame so the next page never shows
        over = over.replace(
            "[0:v]fps=30,",
            f"[0:v]fps=30,tpad=stop_mode=clone:stop_duration={dur - vdur + 0.5:.3f},",
        )
    fc = (
        over + f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo,afade=in:st=0:d=0.15,"
        f"afade=out:st={dur - fo:.3f}:d={fo}[a]"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-v",
            "error",
            "-y",
            "-ss",
            f"{t0:.3f}",
            "-t",
            f"{vdur:.3f}",
            "-i",
            VIDEO,
            "-ss",
            f"{t0 + OFF:.3f}",
            "-t",
            f"{dur:.3f}",
            "-i",
            str(HERE / "nvda.wav"),
            "-loop",
            "1",
            "-t",
            "5.8",
            "-i",
            str(CARDS / f"{sc}.png"),  # unused input when not first
            "-filter_complex",
            fc,
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-c:a",
            "pcm_s16le",
            "-t",
            f"{dur:.3f}",
            str(out).replace(".mp4", ".mkv"),
        ],
        check=True,
    )
    parts.append((sc, t0, t1, dur, str(out).replace(".mp4", ".mkv")))

# Chain crossfades.
inputs, fc, offset = [], [], 0.0
for _, _, _, _, path in parts:
    inputs += ["-i", path]
vlast, alast = "[0:v]", "[0:a]"
for i in range(1, len(parts)):
    offset += parts[i - 1][3] - XF
    fc.append(f"{vlast}[{i}:v]xfade=transition=fade:duration={XF}:offset={offset:.3f}[v{i}]")
    fc.append(f"{alast}[{i}:a]acrossfade=d={XF}[a{i}]")
    vlast, alast = f"[v{i}]", f"[a{i}]"
fc.append(f"{alast}loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[aout]")
out = CLIPS / "act5.mp4"
subprocess.run(
    [
        "ffmpeg",
        "-hide_banner",
        "-v",
        "error",
        "-y",
        *inputs,
        "-filter_complex",
        ";".join(fc),
        "-map",
        vlast,
        "-map",
        "[aout]",
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(out),
    ],
    check=True,
)
for p in parts:
    Path(p[4]).unlink()
seg = [
    {"scene": sc, "log_start": round(t0, 3), "log_end": round(t1, 3), "seconds": round(dur, 2)}
    for sc, t0, t1, dur, _ in parts
]
(CLIPS / "act5-segments.json").write_text(
    json.dumps({"audio_offset": OFF, "crossfade": XF, "segments": seg}, indent=1), encoding="utf-8"
)
total = sum(p[3] for p in parts) - XF * (len(parts) - 1)
print(json.dumps(seg, indent=1), f"\ntotal {total:.1f}s")
