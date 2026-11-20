# Recording the demo GIF

The README does not embed a GIF yet. When you record one, save it as `docs/assets/demo.gif`, then
add `![pr-brief comment on a pull request](docs/assets/demo.gif)` under "What the comment looks
like" in `README.md`.

## What to show (about 15 seconds)

1. A small pull request on a throwaway repository with the workflow from the README installed.
2. The Actions run finishing.
3. The single "PR Brief" comment: summary, commit message, risks, the collapsed checklist opened.
4. A new push, and the same comment being updated (not a second one).

## Rules

- Use a **sandbox repository and a throwaway or revoked key**. Never record real code, real keys or
  a real person's name or e-mail address.
- Check every frame for tokens, secret names and private URLs before publishing.
- Keep it under 2 MB: 800 px wide, 10 to 12 fps.

## Tools (pick one)

- Windows: [ScreenToGif](https://www.screentogif.com/), record the browser window and export GIF.
- Any OS: record an MP4 and convert it with `ffmpeg`:

```bash
ffmpeg -i demo.mp4 -vf "fps=10,scale=800:-1:flags=lanczos" -loop 0 docs/assets/demo.gif
```
