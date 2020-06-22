import tempfile
import textwrap

import pytest

from deckset_inline.inliner import check, InlineError, result_generator


def write_lines_to_file(fileobj, num_lines, line_template=None):
    if line_template is None:
        line_template = "line {} of included file"
    for i in range(num_lines):
        fileobj.write(line_template.format(i + 1) + "\n")
    fileobj.flush()


def test_check_ok():
    file = [
        "line 1",
        "line 2"
    ]
    check(file, clean=False)


def test_check_closing_not_found():
    file = [
        "line 1",
        """<!-- <inline src="foo"> -->"""
    ]
    with pytest.raises(InlineError) as exc_info:
        check(file, clean=False)
        assert "Directive not closed at end of file" in str(exc_info.value)


def test_inline_basic():
    with tempfile.NamedTemporaryFile("w") as ftmp:
        write_lines_to_file(ftmp, 2)

        res = result_generator(textwrap.dedent(f"""\
            head
            <!-- <inline src="{ftmp.name}"> -->
            <!-- </inline> -->
            tail
            """).splitlines(keepends=True))

        assert "".join(res) == textwrap.dedent(f"""\
            head
            <!-- <inline src="{ftmp.name}"> -->
            line 1 of included file
            line 2 of included file
            <!-- </inline> -->
            tail
            """)


def test_inline_verbatim():
    with tempfile.NamedTemporaryFile("w") as ftmp:
        write_lines_to_file(ftmp, 2)

        res = result_generator(textwrap.dedent(f"""\
            head
            <!-- <inline src="{ftmp.name}" verbatim> -->
            <!-- </inline> -->
            tail
            """).splitlines(keepends=True))

        assert "".join(res) == textwrap.dedent(f"""\
            head
            <!-- <inline src="{ftmp.name}" verbatim> -->
            ```
            line 1 of included file
            line 2 of included file
            ```
            <!-- </inline> -->
            tail
            """)


def test_inline_with_start():
    with tempfile.NamedTemporaryFile("w") as ftmp:
        write_lines_to_file(ftmp, 10)

        res = result_generator(textwrap.dedent(f"""\
            head
            <!-- <inline src="{ftmp.name}" start="8"> -->
            <!-- </inline> -->
            tail
            """).splitlines(keepends=True))

        assert "".join(res) == textwrap.dedent(f"""\
            head
            <!-- <inline src="{ftmp.name}" start="8"> -->
            line 8 of included file
            line 9 of included file
            line 10 of included file
            <!-- </inline> -->
            tail
            """)


def test_inline_with_end():
    with tempfile.NamedTemporaryFile("w") as ftmp:
        write_lines_to_file(ftmp, 10)

        res = result_generator(textwrap.dedent(f"""\
            head
            <!-- <inline src="{ftmp.name}" end="3"> -->
            <!-- </inline> -->
            tail
            """).splitlines(keepends=True))

        assert "".join(res) == textwrap.dedent(f"""\
            head
            <!-- <inline src="{ftmp.name}" end="3"> -->
            line 1 of included file
            line 2 of included file
            line 3 of included file
            <!-- </inline> -->
            tail
            """)


def test_inline_with_start_and_end():
    with tempfile.NamedTemporaryFile("w") as ftmp:
        write_lines_to_file(ftmp, 10)

        res = result_generator(textwrap.dedent(f"""\
            head
            <!-- <inline src="{ftmp.name}" start=4 end="6"> -->
            <!-- </inline> -->
            tail
            """).splitlines(keepends=True))

        assert "".join(res) == textwrap.dedent(f"""\
            head
            <!-- <inline src="{ftmp.name}" start=4 end="6"> -->
            line 4 of included file
            line 5 of included file
            line 6 of included file
            <!-- </inline> -->
            tail
            """)


def test_inline_clean():
    with tempfile.NamedTemporaryFile("w") as ftmp:
        write_lines_to_file(ftmp, 10)

        res = result_generator(textwrap.dedent(f"""\
            head
            <!-- <inline src="{ftmp.name}" start=4 end="6"> -->
            <!-- </inline> -->
            tail
            """).splitlines(keepends=True), clean=True)

        assert "".join(res) == textwrap.dedent(f"""\
            head
            <!-- <inline src="{ftmp.name}" start=4 end="6"> -->
            <!-- </inline> -->
            tail
            """)


def test_inline_lang():
    with tempfile.NamedTemporaryFile("w") as ftmp:
        write_lines_to_file(ftmp, 3)

        res = result_generator(textwrap.dedent(f"""\
            head
            <!-- <inline src="{ftmp.name}" lang="java"> -->
            <!-- </inline> -->
            tail
            """).splitlines(keepends=True))

        assert "".join(res) == textwrap.dedent(f"""\
            head
            <!-- <inline src="{ftmp.name}" lang="java"> -->
            ```java
            line 1 of included file
            line 2 of included file
            line 3 of included file
            ```
            <!-- </inline> -->
            tail
            """)


def test_inline_replace_content():
    with tempfile.NamedTemporaryFile("w") as ftmp:
        write_lines_to_file(ftmp, 3)

        res = result_generator(textwrap.dedent(f"""\
            head
            <!-- <inline src="{ftmp.name}"> -->
            Old content to replace
            <!-- </inline> -->
            tail
            """).splitlines(keepends=True))

        assert "".join(res) == textwrap.dedent(f"""\
            head
            <!-- <inline src="{ftmp.name}"> -->
            line 1 of included file
            line 2 of included file
            line 3 of included file
            <!-- </inline> -->
            tail
            """)
