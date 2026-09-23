from verireview.ingestion.anchor import locate_comment_line

CODE = "\n".join(
    [
        "def create_parser(self):",  # 1
        '    """Creates the parser."""',  # 2
        "    parser = Parser(self)",  # 3
        "    return parser",  # 4
        "",  # 5
        "def get_help_option(self):",  # 6
        "    if self._help_option is None:",  # 7
        "        self._help_option = make()",  # 8
        "    return self._help_option",  # 9
        "",  # 10
    ]
)
HUNK = (
    "@@ -1,3 +6,4 @@ class Command:\n"
    "+def get_help_option(self):\n"
    "+    if self._help_option is None:\n"
    "+        self._help_option = make()\n"
    "+    return self._help_option"
)


def test_anchors_last_hunk_line() -> None:
    assert locate_comment_line(CODE, HUNK, "RIGHT", 9) == 9


def test_corrects_a_wrong_original_line() -> None:
    # pallets/click#2811: GitHub said 1053, content was at 1050.
    assert locate_comment_line(CODE, HUNK, "RIGHT", 12) == 9


def test_context_lines_count_as_new_side() -> None:
    hunk = "@@ -2,3 +2,3 @@\n     parser = Parser(self)\n-    return None\n+    return parser"

    assert locate_comment_line(CODE, hunk, "RIGHT", 4) == 4


def test_left_side_comments_are_not_anchored() -> None:
    assert locate_comment_line(CODE, HUNK, "LEFT", 9) is None


def test_hunk_ending_in_deleted_line_is_not_anchored() -> None:
    hunk = "@@ -1,2 +1,1 @@\n def f():\n-    old()"

    assert locate_comment_line(CODE, hunk, None, 2) is None


def test_not_found_returns_none() -> None:
    hunk = "@@ -1 +1 @@\n+this line is nowhere"

    assert locate_comment_line(CODE, hunk, "RIGHT", 1) is None


def test_duplicate_matches_pick_nearest_to_original_line() -> None:
    code = "x = 1\npass\ny = 2\npass\nz = 3\n"
    hunk = "@@ -1 +1 @@\n+pass"

    assert locate_comment_line(code, hunk, "RIGHT", 4) == 4
    assert locate_comment_line(code, hunk, "RIGHT", 1) == 2


def test_duplicate_matches_without_original_line_are_not_guessed() -> None:
    assert locate_comment_line("pass\npass\n", "@@ -1 +1 @@\n+pass", "RIGHT", None) is None


def test_longer_context_wins_over_generic_last_line() -> None:
    code = "    )\nfoo(\n    a,\n    )\n"
    hunk = "@@ -1 +1 @@\n+foo(\n+    a,\n+    )"

    assert locate_comment_line(code, hunk, "RIGHT", 1) == 4
