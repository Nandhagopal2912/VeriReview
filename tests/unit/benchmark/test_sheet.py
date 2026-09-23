import json
import re

from helpers.cases import make_case
from verireview.benchmark.sheet import SHEET_VERSION, render_sheet, sheet_case

HOSTILE = '</script><img src=x onerror="alert(1)"> & <b>bold</b>'


def data_of(html: str) -> dict:  # type: ignore[type-arg]
    match = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S)
    assert match is not None
    return json.loads(match.group(1))  # type: ignore[no-any-return]


def hostile_case():  # type: ignore[no-untyped-def]
    case = make_case("x = 1  # </script>\n", "x = 2\n", 1)
    comment = case.thread.comments[0].model_copy(update={"body": HOSTILE})
    return case.model_copy(
        update={"thread": case.thread.model_copy(update={"comments": [comment]})}
    )


def test_untrusted_content_cannot_close_the_data_block() -> None:
    html = render_sheet([sheet_case("evil", hostile_case())], "b")

    assert html.count("</script>") == 2  # only the page's own two script elements
    assert "<img" not in html
    assert data_of(html)["cases"][0]["thread"][0]["body"] == HOSTILE  # round-trips exactly


def test_the_page_loads_nothing_from_the_network() -> None:
    html = render_sheet([], "b")

    assert "default-src 'none'" in html
    assert not re.search(r"(src|href)=\"https?:", html)


def test_sheet_case_shows_the_excerpt_diff_and_tests() -> None:
    before = "".join(f"line{i} = {i}\n" for i in range(1, 80))
    after = before.replace("line40 = 40", "line40 = 41")
    case = make_case(before, after, 40, tests={"tests/t.py": "def test_a():\n    pass\n"})
    from verireview.ingestion import make_unified_diff

    case = case.model_copy(
        update={"unified_diff": make_unified_diff(before, after, "m.py", "m.py")}
    )

    sc = sheet_case("c", case)

    assert sc.before_excerpt[0] == (15, "line15 = 15") and sc.before_excerpt[-1] == (
        65,
        "line65 = 65",
    )
    assert "+line40 = 41" in sc.diff
    assert sc.test_diffs[0][0] == "tests/t.py" and "+def test_a():" in sc.test_diffs[0][1]


def test_modes_and_reference() -> None:
    ref = {"verdict": "SATISFIED", "rationale": "because", "requirements": []}
    html = render_sheet(
        [sheet_case("c", make_case("x = 1\n", "x = 1\n", 1), ref)], "cal", "calibration"
    )

    data = data_of(html)
    assert data["mode"] == "calibration" and data["version"] == SHEET_VERSION
    assert data["cases"][0]["reference"]["verdict"] == "SATISFIED"
    assert "<title>Calibration · cal</title>" in html
