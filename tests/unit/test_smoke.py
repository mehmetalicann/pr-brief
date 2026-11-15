import pytest

import pr_brief
from pr_brief.__main__ import main


def test_package_has_version() -> None:
    assert pr_brief.__version__


def test_main_requires_a_diff_argument() -> None:
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
