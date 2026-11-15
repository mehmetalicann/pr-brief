from collections.abc import Callable

import pytest

from pr_brief.core.diff import FileDiff, parse_diff
from pr_brief.core.filters import MAX_FILES, filter_files, matches_glob


def file(path: str, *, binary: bool = False, status: str = "modified") -> FileDiff:
    return FileDiff(
        old_path=None if status == "added" else path,
        new_path=None if status == "deleted" else path,
        status=status,  # type: ignore[arg-type]
        hunks=(),
        is_binary=binary,
        additions=0,
        deletions=0,
    )


@pytest.mark.parametrize(
    ("path", "pattern", "expected"),
    [
        ("a/b/c.min.js", "*.min.js", True),  # no slash: basename at any depth
        ("c.min.js", "*.min.js", True),
        ("src/app.py", "*.min.js", False),
        ("docs/a.md", "docs/**", True),
        ("docs/x/y/a.md", "docs/**", True),
        ("other/docs/a.md", "docs/**", False),  # anchored when the pattern has a slash
        ("other/docs/a.md", "**/docs/**", True),
        ("vendor/lib/x.py", "vendor/", True),  # trailing slash: directory anywhere
        ("pkg/vendor/x.py", "vendor/", True),
        ("src/vendors.py", "vendor/", False),
        ("src/a.py", "src/?.py", True),
        ("src/ab.py", "src/?.py", False),
        ("src/a/b.py", "src/*.py", False),  # * does not cross directories
    ],
)
def test_matches_glob(path: str, pattern: str, expected: bool) -> None:
    assert matches_glob(path, pattern) is expected


def test_default_ignores_lockfiles_generated_and_images() -> None:
    paths = [
        "package-lock.json",
        "web/yarn.lock",
        "uv.lock",
        "dist/bundle.js",
        "app/static/app.min.js",
        "assets/logo.png",
        "node_modules/x/index.js",
        "vendor/dep/a.go",
        "api/service.pb.go",
        "api/service_pb2.py",
    ]
    result = filter_files([file(p) for p in paths] + [file("src/main.py")], ignore=[])
    assert [f.path for f in result.kept] == ["src/main.py"]
    assert {s.path for s in result.skipped} == set(paths)
    assert all(s.reason == "ignored by default" for s in result.skipped)


def test_user_ignore_globs_apply_and_are_reported() -> None:
    result = filter_files([file("src/a.py"), file("gen/b.py")], ignore=["gen/**"])
    assert [f.path for f in result.kept] == ["src/a.py"]
    assert result.skipped[0].reason == "ignored by config"


def test_binary_files_are_skipped() -> None:
    result = filter_files([file("data.bin", binary=True)], ignore=[])
    assert result.kept == ()
    assert result.skipped[0].reason == "binary"


def test_file_count_cap_skips_the_rest_with_reason() -> None:
    files = [file(f"src/f{i}.py") for i in range(MAX_FILES + 5)]
    result = filter_files(files, ignore=[])
    assert len(result.kept) == MAX_FILES
    assert [s.reason for s in result.skipped] == ["file limit exceeded"] * 5


def test_blank_user_patterns_are_ignored() -> None:
    result = filter_files([file("src/a.py")], ignore=["", "  "])
    assert len(result.kept) == 1


def test_medium_patch_keeps_only_reviewable_files(load_diff: Callable[[str], str]) -> None:
    result = filter_files(parse_diff(load_diff("medium.patch")), ignore=[])
    assert [f.path for f in result.kept] == [
        "src/app/calc.py",
        "src/app/util.py",
        "src/app/legacy.py",
        "docs/guide.md",
        "b.txt",
        "tests/test_calc.py",
    ]
    reasons = {s.path: s.reason for s in result.skipped}
    assert reasons == {
        "package-lock.json": "ignored by default",
        "assets/logo.png": "binary",
    }
