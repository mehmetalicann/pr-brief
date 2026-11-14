import pr_brief
from pr_brief.__main__ import main


def test_package_has_version() -> None:
    assert pr_brief.__version__


def test_main_skeleton_exits_zero() -> None:
    assert main() == 0
