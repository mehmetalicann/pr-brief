# The demo GIF

`docs/assets/demo.gif` is **generated**, not recorded:

```bash
.venv/Scripts/python scripts/make_demo_gif.py     # needs ffmpeg on PATH and Edge or Chrome
```

The script runs the project's own pipeline (mock provider, canned model answers) on a tiny demo
diff, draws a pull request page around the resulting comment, screenshots it with headless
Edge/Chrome (set `BROWSER` to pick another executable) and joins the frames with ffmpeg. No Python
dependency is involved, and every frame is labelled "Illustration, not a screen recording".

Edit the story in `scripts/make_demo_gif.py` (`BRIEF_FIRST`, `BRIEF_SECOND`, `build_scenes`), then
rerun it. The GIF must stay under 2 MB and 800 px wide (`tests/unit/test_demo_gif.py` checks it).

## If you ever record a real one

Use a sandbox repository and a throwaway or revoked key. Never record real code, real keys or a
real person's name or e-mail address, and check every frame for tokens, secret names and private
URLs. ScreenToGif (Windows) works; keep it under 2 MB, 800 px wide, 10 to 12 fps.
