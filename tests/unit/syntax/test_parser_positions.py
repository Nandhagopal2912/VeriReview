"""Regression: reading ``Point.row`` / ``Point.column`` crashes tree-sitter 0.26 (Windows).

Found in Phase 9b on a 42 KB real-world file: the attribute getters corrupt the heap after enough
calls (`0xc0000374` / access violation), which would kill the API process. The same synthetic
file used here crashes reliably with attribute access and never with tuple indexing.
"""

import re
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src" / "verireview"

STRESS = """
from verireview.syntax.parser import end_line, parse, start_line

code = "".join(
    f"class C{i}:\\n    def m(self, a, b=1):\\n        if a > b:\\n"
    f"            return [x * 2 for x in range(a)]\\n        return {{'k': a}}\\n\\n"
    for i in range(300)
)

def walk(node):
    for child in node.named_children:
        start_line(child)
        end_line(child)
        walk(child)

for _ in range(20):
    walk(parse(code).root_node)
print("ok")
"""


def test_line_helpers_survive_a_large_tree() -> None:
    result = subprocess.run(  # noqa: S603 - fixed interpreter and script
        [sys.executable, "-c", STRESS], capture_output=True, text=True, timeout=300
    )

    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip() == "ok"


def test_no_point_attribute_access_in_the_code() -> None:
    offenders = [
        f"{path.relative_to(SRC)}:{number}"
        for path in SRC.rglob("*.py")
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if re.search(r"_point\.(row|column)\b", line)
    ]

    assert offenders == []
