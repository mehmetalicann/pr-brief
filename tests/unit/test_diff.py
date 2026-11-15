from pathlib import Path

from pr_brief.core.diff import parse_diff

FIXTURES = Path(__file__).parent.parent / "fixtures" / "diffs"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_empty_input_returns_no_files() -> None:
    assert parse_diff("") == []
    assert parse_diff("   \n\n") == []


def test_small_patch_single_modified_file() -> None:
    (f,) = parse_diff(load("small.patch"))
    assert f.path == "src/app/greet.py"
    assert f.status == "modified"
    assert (f.additions, f.deletions) == (3, 1)
    assert len(f.hunks) == 1
    h = f.hunks[0]
    assert (h.old_start, h.old_count, h.new_start, h.new_count) == (1, 2, 1, 4)
    assert h.lines[0] == " def greet(name):"


def test_medium_patch_file_statuses() -> None:
    files = {f.path: f for f in parse_diff(load("medium.patch"))}
    assert list(files) == [
        "src/app/calc.py",
        "src/app/util.py",
        "src/app/legacy.py",
        "docs/guide.md",
        "b.txt",
        "package-lock.json",
        "assets/logo.png",
        "tests/test_calc.py",
    ]
    assert files["src/app/calc.py"].status == "modified"
    assert len(files["src/app/calc.py"].hunks) == 2
    assert files["src/app/util.py"].status == "added"
    assert files["src/app/util.py"].old_path is None
    assert files["src/app/legacy.py"].status == "deleted"
    assert files["src/app/legacy.py"].new_path is None
    assert files["docs/guide.md"].status == "renamed"
    assert files["docs/guide.md"].old_path == "docs/intro.md"
    assert files["assets/logo.png"].is_binary
    assert files["assets/logo.png"].hunks == ()


def test_pure_rename_has_no_hunks() -> None:
    f = next(f for f in parse_diff(load("medium.patch")) if f.path == "b.txt")
    assert f.status == "renamed"
    assert f.old_path == "a.txt"
    assert f.hunks == ()
    assert (f.additions, f.deletions) == (0, 0)


def test_no_newline_marker_is_kept_but_not_counted() -> None:
    text = (
        "diff --git a/x.txt b/x.txt\n"
        "index 1..2 100644\n"
        "--- a/x.txt\n"
        "+++ b/x.txt\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "\\ No newline at end of file\n"
        "+new\n"
        "\\ No newline at end of file\n"
    )
    (f,) = parse_diff(text)
    assert (f.additions, f.deletions) == (1, 1)
    assert "\\ No newline at end of file" in f.hunks[0].lines


def test_hunk_counts_protect_against_lookalike_headers() -> None:
    # A removed line that itself starts with "-- " / an added line starting with "++ "
    # must not be mistaken for file headers.
    text = (
        "diff --git a/s.sql b/s.sql\n"
        "--- a/s.sql\n"
        "+++ b/s.sql\n"
        "@@ -1,3 +1,3 @@\n"
        "--- comment\n"
        "+++ comment\n"
        " keep\n"
        "-gone\n"
        "+kept\n"
    )
    (f,) = parse_diff(text)
    assert f.path == "s.sql"
    assert (f.additions, f.deletions) == (2, 2)


def test_crlf_input_is_normalised() -> None:
    (f,) = parse_diff(load("small.patch").replace("\n", "\r\n"))
    assert f.path == "src/app/greet.py"
    assert all("\r" not in line for line in f.hunks[0].lines)


def test_quoted_paths_and_spaces() -> None:
    text = (
        'diff --git "a/dir/we\\tird.txt" "b/dir/we\\tird.txt"\n'
        "index 1..2 100644\n"
        '--- "a/dir/we\\tird.txt"\n'
        '+++ "b/dir/we\\tird.txt"\n'
        "@@ -1 +1 @@\n"
        "-a\n"
        "+b\n"
        "diff --git a/my file.txt b/my file.txt\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/my file.txt\n"
        "@@ -0,0 +1 @@\n"
        "+hi\n"
    )
    paths = [f.path for f in parse_diff(text)]
    assert paths == ["dir/we\tird.txt", "my file.txt"]


def test_git_binary_patch_marks_binary_and_skips_payload() -> None:
    text = (
        "diff --git a/x.bin b/x.bin\n"
        "index 1..2 100644\n"
        "GIT binary patch\n"
        "literal 3\n"
        "Kc${Nk\n"
        "\n"
        "diff --git a/y.txt b/y.txt\n"
        "--- a/y.txt\n"
        "+++ b/y.txt\n"
        "@@ -1 +1 @@\n"
        "-a\n"
        "+b\n"
    )
    x, y = parse_diff(text)
    assert x.is_binary
    assert not y.is_binary


def test_mode_only_change_is_modified_without_hunks() -> None:
    text = "diff --git a/run.sh b/run.sh\nold mode 100644\nnew mode 100755\n"
    (f,) = parse_diff(text)
    assert f.status == "modified"
    assert f.hunks == ()


def test_truncated_hunk_does_not_crash() -> None:
    text = "diff --git a/t.txt b/t.txt\n--- a/t.txt\n+++ b/t.txt\n@@ -1,5 +1,5 @@\n a\n-b\n"
    (f,) = parse_diff(text)
    assert f.deletions == 1


def test_blank_context_line_without_leading_space() -> None:
    # Some tools strip the single trailing space of an empty context line.
    text = "diff --git a/t.txt b/t.txt\n--- a/t.txt\n+++ b/t.txt\n@@ -1,3 +1,3 @@\n a\n\n-b\n+c\n"
    (f,) = parse_diff(text)
    assert (f.additions, f.deletions) == (1, 1)
    assert f.hunks[0].lines == (" a", " ", "-b", "+c")


def test_render_round_trips_through_the_parser() -> None:
    for name in ("small.patch", "medium.patch"):
        files = parse_diff(load(name))
        rendered = "\n".join(f.render() for f in files) + "\n"
        again = parse_diff(rendered)
        assert [(f.path, f.status, f.additions, f.deletions) for f in again] == [
            (f.path, f.status, f.additions, f.deletions) for f in files
        ]


def test_non_ascii_paths_quoted_with_octal_escapes() -> None:
    # git quotes a path with u-umlaut as octal bytes (\303\274) unless core.quotePath=false
    text = (
        r'diff --git "a/dir/\303\274.txt" "b/dir/\303\274.txt"'
        "\n"
        "new file mode 100644\n"
        r'Binary files /dev/null and "b/dir/\303\274.txt" differ'
        "\n"
    )
    (f,) = parse_diff(text)
    assert f.path == "dir/\u00fc.txt"
    assert f.is_binary


def test_unparseable_header_does_not_crash() -> None:
    (f,) = parse_diff("diff --git garbage\n")
    assert f.path == ""
