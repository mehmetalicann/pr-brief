"""The demo GIF is generated from the real renderer; its HTML must be safe and the file sane."""

from __future__ import annotations

import importlib.util
import re
import struct
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
GIF = ROOT / "docs" / "assets" / "demo.gif"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "make_demo_gif", ROOT / "scripts" / "make_demo_gif.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["make_demo_gif"] = module
    spec.loader.exec_module(module)
    return module


demo = _load()


def test_markdown_is_escaped_before_anything_is_formatted() -> None:
    html = demo.markdown_to_html("<script>alert(1)</script> & **bold** `x<y` [t](https://a.b/c)")
    assert "<script" not in html and "&lt;script&gt;" in html
    assert "<strong>bold</strong>" in html and "<code>x&lt;y</code>" in html
    assert '<a href="https://a.b/c">t</a>' in html


def test_javascript_links_are_not_turned_into_anchors() -> None:
    html = demo.markdown_to_html("[x](javascript:alert(1))")
    assert "<a " not in html


def test_the_structure_of_a_real_comment_survives_the_conversion() -> None:
    first, _ = demo.build_comments()
    html = demo.markdown_to_html(first)
    assert "<h2>PR Brief</h2>" in html
    assert "<details>" in html and "<summary>Review checklist" in html
    assert "<pre>" in html and "fix(greet): reject empty names" in html
    assert "pr-brief:v1" not in html  # the hidden marker is not visible text
    assert html.count("<details>") == html.count("</details>")


def test_the_comments_come_from_the_real_renderer_and_differ_after_the_push() -> None:
    first, second = demo.build_comments()
    assert first.startswith("<!-- pr-brief:v1 -->") and second.startswith("<!-- pr-brief:v1 -->")
    assert first != second and "whitespace" in second


def test_scenes_tell_the_story_with_exactly_one_comment() -> None:
    scenes = demo.build_scenes()
    assert len(scenes) >= 5
    assert "running" in scenes[0].html.lower()
    counts = [s.html.count('class="comment"') for s in scenes]
    assert counts[0] == 0 and counts[-1] == 1 and max(counts) == 1
    assert "edited" in scenes[-1].html
    assert sum(s.seconds for s in scenes) <= 20


def test_scenes_contain_nothing_personal_or_secret() -> None:
    text = "".join(s.html for s in demo.build_scenes()).lower()
    for needle in ("@gmail", "c:\\users", "/c/users", "ghp_", "aiza", "sk-", "api_key", "secret"):
        assert needle not in text, needle
    assert "illustration" in text  # visible in every frame, so nobody mistakes it for a recording


def test_the_readme_embeds_the_gif_and_the_file_is_a_small_800px_gif() -> None:
    assert "docs/assets/demo.gif" in (ROOT / "README.md").read_text(encoding="utf-8")
    data = GIF.read_bytes()
    assert data[:6] == b"GIF89a"
    width, height = struct.unpack("<HH", data[6:10])
    assert width == 800 and 400 <= height <= 1400
    assert len(data) <= 2 * 1024 * 1024
    assert re.search(rb"NETSCAPE2\.0", data), "the GIF must loop"
