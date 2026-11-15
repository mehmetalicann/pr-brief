from pr_brief.core.chunker import MAX_CHUNKS, estimate_tokens, plan_chunks
from pr_brief.core.diff import FileDiff, Hunk


def make_file(path: str, n_lines: int, width: int = 40) -> FileDiff:
    lines = tuple("+" + ("x" * width) + str(i) for i in range(n_lines))
    hunk = Hunk(f"@@ -0,0 +1,{n_lines} @@", 0, 0, 1, n_lines, lines)
    return FileDiff(
        old_path=None,
        new_path=path,
        status="added",
        hunks=(hunk,),
        is_binary=False,
        additions=n_lines,
        deletions=0,
    )


def test_estimate_tokens_is_deterministic_and_monotonic() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2
    assert estimate_tokens("a" * 400) == 100


def test_small_diff_is_one_chunk() -> None:
    plan = plan_chunks([make_file("a.py", 3), make_file("b.py", 3)], budget_tokens=2000)
    assert len(plan.chunks) == 1
    assert [i.path for i in plan.chunks[0].items] == ["a.py", "b.py"]
    assert plan.omitted == ()
    assert not plan.truncated


def test_chunks_never_exceed_budget_and_keep_file_boundaries() -> None:
    files = [make_file(f"f{i}.py", 20) for i in range(6)]
    budget = 500
    plan = plan_chunks(files, budget_tokens=budget)
    assert len(plan.chunks) > 1
    for chunk in plan.chunks:
        assert chunk.tokens <= budget
    seen = [i.path for c in plan.chunks for i in c.items]
    assert seen == [f"f{i}.py" for i in range(6)]  # order kept, no file split across chunks


def test_planning_is_deterministic() -> None:
    files = [make_file(f"f{i}.py", 15) for i in range(8)]
    assert plan_chunks(files, budget_tokens=400) == plan_chunks(files, budget_tokens=400)


def test_giant_file_is_truncated_with_explicit_marker() -> None:
    plan = plan_chunks([make_file("big.py", 5000)], budget_tokens=600)
    (chunk,) = plan.chunks
    (item,) = chunk.items
    assert item.truncated
    assert chunk.tokens <= 600
    assert "truncated" in item.text
    assert plan.truncated == ("big.py",)


def test_50k_token_diff_yields_bounded_number_of_chunks() -> None:
    files = [make_file(f"mod/f{i}.py", 100, width=50) for i in range(40)]
    total = sum(estimate_tokens(f.render()) for f in files)
    assert total > 50_000
    plan = plan_chunks(files, budget_tokens=5000)
    assert 1 < len(plan.chunks) <= MAX_CHUNKS
    assert plan.omitted  # what does not fit is listed, not silently dropped
    packed = {i.path for c in plan.chunks for i in c.items}
    assert packed.isdisjoint(plan.omitted)
    assert packed | set(plan.omitted) == {f.path for f in files}


def test_empty_input_gives_empty_plan() -> None:
    plan = plan_chunks([], budget_tokens=1000)
    assert plan.chunks == ()
    assert plan.omitted == ()
