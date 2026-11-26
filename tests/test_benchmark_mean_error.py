import pytest

from rodar_suite_benchmark import _mean_error


@pytest.mark.parametrize(("contents", "expected"), [
    (None, None),
    ("", None),
    ("erro_estimado_pct\n", None),
    ("erro_estimado_pct\nunknown\n", None),
    ("erro_estimado_pct\nunknown\n2.5\n", 2.5),
    ("erro_estimado_pct\n1.5\n4.5\n", 3.0),
])
def test_mean_error(tmp_path, contents, expected):
    if contents is not None:
        (tmp_path / "resumo_peixes.csv").write_text(contents, encoding="utf-8")

    assert _mean_error(tmp_path) == expected
