# README GIF

Makes `docs/images/disability-access-charts-tour.gif`, the eight-step tour of
`disability-access-charts` in the main README. Every output in it comes from a real run.

1. In a fresh environment: `pip install disability-access-charts`, saving the last three lines of its output as `pip.txt`.
2. `python frames.py pip.txt` with that environment's Python: runs each step and writes `frames.json`.
3. `node render-gif.mjs <folder with frames.json>` (Playwright): one PNG per frame in `png/`.
4. Assemble with ffmpeg (each step held 6 to 12 seconds so it can be read):

```
ffmpeg -f concat -safe 0 -i png/list.txt -vf "fps=1,scale=1000:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=64:stats_mode=full[p];[b][p]paletteuse=dither=none" -loop 0 disability-access-charts-tour.gif
```

`png/list.txt` lists each PNG with a `duration` line (seconds): 4, 6, 8, 8, 12, 9, 7, 10, 7, 5.
If the library's output changes, rebuild the GIF and update the text version in the README.
