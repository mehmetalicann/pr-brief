"""Builds docs/assets/demo.gif from the real comment renderer (no screen recording needed).

    .venv/Scripts/python scripts/make_demo_gif.py            # writes docs/assets/demo.gif

It runs the project's own pipeline (mock provider, canned model text) on a tiny demo diff, shows the
resulting Markdown as a pull request page in headless Edge/Chrome and joins the frames with ffmpeg.
No Python dependency is added: it needs `ffmpeg` on PATH and Edge or Chrome (or set BROWSER).
Every frame says "illustration": the page is drawn, the comment text is the real renderer's output
but the model answer is canned.
"""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

WIDTH, HEIGHT = 800, 900
REPO = "octo/demo"
DEMO_DIFF = """diff --git a/greeter.py b/greeter.py
--- a/greeter.py
+++ b/greeter.py
@@ -1,2 +1,4 @@
 def greet(name):
+    if not name:
+        raise ValueError("name must not be empty")
     return f"Hello, {name}!"
"""

BRIEF_FIRST = {
    "summary": "Adds input validation to `greet()` and a test for the empty-name case.",
    "changes": [
        "`greet()` now raises `ValueError` for an empty name",
        "New test for the error path",
    ],
    "commit_message": {
        "type": "fix",
        "scope": "greet",
        "subject": "reject empty names",
        "body": None,
    },
    "risks": [
        {
            "level": "low",
            "area": "api",
            "note": "callers that passed an empty string now get an exception",
        }
    ],
    "review_checklist": ["Check callers of `greet()` for empty input"],
    "missing_tests": [],
}
BRIEF_SECOND = {
    **BRIEF_FIRST,
    "summary": "Validates `greet()` input, with tests for empty and whitespace-only names.",
    "changes": [*BRIEF_FIRST["changes"], "Whitespace-only names are rejected as well"],
    "review_checklist": [
        *BRIEF_FIRST["review_checklist"],
        "Confirm whitespace-only names are invalid",
    ],
}

CSS = """
*{box-sizing:border-box}body{margin:0;background:#f4f5f7;color:#1f2328;
font:14px/1.5 -apple-system,"Segoe UI",Helvetica,Arial,sans-serif}
.wrap{width:800px;padding:14px 28px}.note{font-size:11px;color:#6b7280;text-align:right}
.crumb{color:#57606a;margin-top:2px}h1{font-size:24px;margin:6px 0 8px;font-weight:600}
h1 .num{color:#6b7280;font-weight:400}.meta{color:#57606a;margin-bottom:12px}
.pill{display:inline-block;padding:1px 10px;border-radius:12px;color:#fff;font-weight:600;
font-size:12px;margin-right:6px}.open{background:#1a7f37}
.checks{background:#fff;border:1px solid #d0d7de;border-radius:6px;padding:8px 14px;
margin-bottom:14px}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:8px}
.run{background:#d4a72c}.ok{background:#1a7f37}.banner{background:#ddf4ff;border:1px solid #54aeff;
border-radius:6px;padding:6px 12px;margin-bottom:12px;color:#0969da}
.box{background:#fff;border:1px solid #d0d7de;border-radius:6px;margin-bottom:14px}
.box .head{background:#f6f8fa;border-bottom:1px solid #d0d7de;padding:6px 14px;color:#57606a;
border-radius:6px 6px 0 0}.box .body{padding:4px 16px 10px}
.body h2{font-size:20px;margin:10px 0 6px;
padding-bottom:4px;border-bottom:1px solid #d8dee4}.body h3{font-size:15px;margin:12px 0 4px}
.body p{margin:6px 0}.body ul{margin:4px 0;padding-left:22px}.body li{margin:2px 0}
.body li input{margin-right:6px}.body code{background:#eff1f3;border-radius:4px;padding:1px 5px;
font:12.5px Consolas,monospace}.body pre{background:#f6f8fa;border-radius:6px;padding:8px 12px;
margin:6px 0}.body pre code{background:none;padding:0}.body details{margin:8px 0}
.body summary{cursor:pointer;color:#0969da}.body hr{border:0;border-top:1px solid #d8dee4}
.body small{color:#6b7280}.edited{color:#6b7280;font-style:italic}.dim{opacity:.45}
.caption{position:fixed;left:0;bottom:0;width:800px;background:#1f2328;color:#fff;
padding:10px 28px;font-size:15px}
"""


@dataclass(frozen=True)
class Scene:
    name: str
    html: str
    seconds: float


# --- Markdown (the comment) -> HTML ------------------------------------------------------------


def _inline(text: str) -> str:
    """Escape first, then format: nothing from the comment can ever become markup."""
    escaped = html.escape(text, quote=False)
    out: list[str] = []
    for index, part in enumerate(re.split(r"(`[^`]+`)", escaped)):
        if index % 2:
            out.append(f"<code>{part[1:-1]}</code>")
            continue
        part = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", part)
        part = re.sub(r'\[([^\]]+)\]\((https://[^)\s"]+)\)', r'<a href="\2">\1</a>', part)
        out.append(part)
    return "".join(out)


def markdown_to_html(markdown: str) -> str:
    """The small subset of Markdown that pr-brief's comment uses."""
    out: list[str] = []
    in_list = False
    lines = iter(markdown.splitlines())

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("<!--") or not stripped:
            close_list()
        elif stripped.startswith("```"):
            close_list()
            code = []
            for inner in lines:
                if inner.strip().startswith("```"):
                    break
                code.append(inner)
            out.append(f"<pre><code>{html.escape(chr(10).join(code), quote=False)}</code></pre>")
        elif stripped in ("<details>", "</details>"):
            close_list()
            out.append(stripped)
        elif m := re.fullmatch(r"<summary>(.*)</summary>", stripped):
            out.append(f"<summary>{_inline(m.group(1))}</summary>")
        elif m := re.fullmatch(r"<sub>(.*)</sub>", stripped):
            out.append(f"<p><small>{_inline(m.group(1))}</small></p>")
        elif stripped == "---":
            close_list()
            out.append("<hr>")
        elif m := re.fullmatch(r"(#{2,3}) (.*)", stripped):
            close_list()
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
        elif m := re.fullmatch(r"- \[ \] (.*)", stripped):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f'<li><input type="checkbox" disabled> {_inline(m.group(1))}</li>')
        elif stripped.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(stripped[2:])}</li>")
        else:
            close_list()
            out.append(f"<p>{_inline(stripped)}</p>")
    close_list()
    return "\n".join(out)


# --- the real comments ---------------------------------------------------------------------------


def build_comments() -> tuple[str, str]:
    """Render two briefs with the project's own pipeline (mock provider, canned answers)."""
    from pr_brief.__main__ import run
    from pr_brief.config import load_settings
    from pr_brief.core.prompts import PRMeta
    from pr_brief.providers.mock import MockProvider

    with tempfile.TemporaryDirectory() as tmp:
        settings = load_settings({"PR_BRIEF_PROVIDER": "mock"}, base_dir=Path(tmp))
    meta = PRMeta(title="Add input validation to greet()", body=None, base="main", head="feature")
    comments = []
    for brief in (BRIEF_FIRST, BRIEF_SECOND):
        provider = MockProvider([json.dumps(brief)])
        comments.append(run(DEMO_DIFF, settings, provider, meta, repo=REPO))
    return comments[0], comments[1]


# --- scenes ----------------------------------------------------------------------------------


def _page(*, check: str, timeline: str, banner: str = "", caption: str = "") -> str:
    dot = "ok" if check == "ok" else "run"
    label = "PR Brief: successful" if check == "ok" else "PR Brief: running..."
    banner_html = f'<div class="banner">{banner}</div>' if banner else ""
    caption_html = f'<div class="caption">{caption}</div>' if caption else ""
    return f"""<!doctype html><meta charset="utf-8"><title>demo</title><style>{CSS}</style>
<div class="wrap"><div class="note">Illustration, not a screen recording</div>
<div class="crumb">{REPO} / Pull requests</div>
<h1>Add input validation to greet() <span class="num">#7</span></h1>
<div class="meta"><span class="pill open">Open</span> feature into main</div>
{banner_html}<div class="checks"><span class="dot {dot}"></span>{label}</div>
<div class="box"><div class="head"><b>octocat</b> opened this pull request</div>
<div class="body"><p>Reject empty names in <code>greet()</code>.</p></div></div>
{timeline}</div>{caption_html}"""


def _comment_box(
    markdown: str, *, edited: bool = False, open_checklist: bool = False, dim: bool = False
) -> str:
    body = markdown_to_html(markdown)
    if open_checklist:
        body = body.replace("<details>", "<details open>", 1)
    tag = ' <span class="edited">(edited)</span>' if edited else ""
    return (
        f'<div class="comment"><div class="box{" dim" if dim else ""}">'
        f'<div class="head"><b>github-actions</b> bot commented{tag}</div>'
        f'<div class="body">{body}</div></div></div>'
    )


def build_scenes() -> list[Scene]:
    first, second = build_comments()
    return [
        Scene(
            "opened",
            _page(check="run", timeline="", caption="1. Open a pull request: the workflow starts"),
            1.6,
        ),
        Scene(
            "passed",
            _page(check="ok", timeline="", caption="2. The check finishes in seconds"),
            1.4,
        ),
        Scene(
            "comment",
            _page(
                check="ok",
                timeline=_comment_box(first),
                caption="3. One comment: summary, commit message, risks",
            ),
            3.2,
        ),
        Scene(
            "checklist",
            _page(
                check="ok",
                timeline=_comment_box(first, open_checklist=True),
                caption="3. ...and a review checklist",
            ),
            3.2,
        ),
        Scene(
            "push",
            _page(
                check="run",
                timeline=_comment_box(first, dim=True),
                banner="octocat pushed 1 new commit: Reject whitespace-only names",
                caption="4. A new push triggers the workflow again",
            ),
            2.2,
        ),
        Scene(
            "updated",
            _page(
                check="ok",
                timeline=_comment_box(second, edited=True, open_checklist=True),
                caption="5. The same comment is edited in place: still one comment",
            ),
            4.0,
        ),
    ]


# --- rendering ---------------------------------------------------------------------------------


def _find_browser() -> str:
    candidates = [
        os.environ.get("BROWSER", ""),
        shutil.which("msedge") or "",
        shutil.which("chrome") or "",
    ]
    for base in (os.environ.get("PROGRAMFILES(X86)", ""), os.environ.get("PROGRAMFILES", "")):
        if base:
            candidates += [
                f"{base}/Microsoft/Edge/Application/msedge.exe",
                f"{base}/Google/Chrome/Application/chrome.exe",
            ]
    candidates += [shutil.which("google-chrome") or "", shutil.which("chromium") or ""]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise SystemExit("No Edge or Chrome found: set BROWSER to its executable path.")


def render(out: Path) -> None:
    browser, ffmpeg = _find_browser(), shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is not on PATH.")
    scenes = build_scenes()
    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        lines = []
        for index, scene in enumerate(scenes):
            page, png = tmp / f"{index}.html", tmp / f"{index}.png"
            page.write_text(scene.html, encoding="utf-8")
            subprocess.run(  # noqa: S603 - fixed arguments, local files only
                [
                    browser,
                    "--headless=new",
                    "--disable-gpu",
                    "--hide-scrollbars",
                    "--force-device-scale-factor=1",
                    f"--user-data-dir={tmp / 'profile'}",
                    f"--window-size={WIDTH},{HEIGHT}",
                    f"--screenshot={png}",
                    page.as_uri(),
                ],
                check=True,
                capture_output=True,
                timeout=90,
            )
            lines += [f"file '{png.as_posix()}'", f"duration {scene.seconds}"]
        lines.append(f"file '{(tmp / f'{len(scenes) - 1}.png').as_posix()}'")
        (tmp / "list.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(  # noqa: S603 - fixed arguments, local files only
            [
                ffmpeg,
                "-y",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(tmp / "list.txt"),
                "-vf",
                f"fps=10,scale={WIDTH}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];"
                "[b][p]paletteuse=dither=none",
                "-loop",
                "0",
                str(out),
            ],
            check=True,
            capture_output=True,
            timeout=180,
        )
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    render(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "assets" / "demo.gif")
